# Odyssey Support (Print .sl1 resin files with Odyssey)
#
# Copyright (C) 2023 Ada Phillips <ragwafire99@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import os, logging, io, json, requests

class Odyssey:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.printer.register_event_handler("klippy:shutdown",
                                            self.handle_shutdown)

        self.url = config.get('url')
        
        # Print Stat Tracking
        self.print_stats = self.printer.load_object(config, 'print_stats')
        
        # Work timer
        self.reactor = self.printer.get_reactor()
        self.must_pause = False

        self.work_timer = self.reactor.register_timer(
            self.odyssey_work_tracker, self.reactor.NEVER
        )

        self.printing = False

        self.status = self.load_status()

        
        self.gcode = self.printer.lookup_object('gcode')

        self.gcode.register_command(
            "ODYSSEY_START",
            self.cmd_START,
            desc=self.cmd_START_help)
        self.gcode.register_command(
            "ODYSSEY_CANCEL_PRINT",
            self.cmd_CANCEL,
            desc=self.cmd_CANCEL_help)
        self.gcode.register_command(
            "ODYSSEY_PAUSE",
            self.cmd_PAUSE,
            desc=self.cmd_PAUSE_help)
        self.gcode.register_command(
            "ODYSSEY_RESUME",
            self.cmd_RESUME,
            desc=self.cmd_RESUME_help)
        #self.gcode.register_command(
        #    "ODYSSEY_STATUS",
        #    self.cmd_PAUSE,
        #    desc=self.cmd_PAUSE_help)
        #self.gcode.register_command(
        #    "LIST_FILES",
        #    self.cmd_LIST_FILES,
        #    desc=self.cmd_LIST_FILES_help)
    

    def handle_shutdown(self):
        try:
            response = requests.post(f"{self.url}/shutdown")
        except:
            pass


    def stats(self, eventtime):
        return False, ""

    def load_status(self):
        try:
            response = requests.get(f"{self.url}/status")
            try:
                return response.json()
            except:
                return {
                    f"Error {response.status_code}": {}
                }
        except:
            return {'Communication Error': {}}
    
    def get_status(self, eventtime):
        self.status = self.load_status()
        for status in self.status:
            ret = {
                "odyssey_status": status,
            }

            status_details = self.status.get(status, {})
            print_data = status_details.get('print_data', {})
            file_data = print_data.get('file_data', {})
            if status == "Printing":
                ret.update({
                    'file_path': f"{file_data.get('location_category')}/{file_data.get('name')}",
                    'is_active': not status_details.get('paused'),
                    'file_position': status_details.get('layer'),
                    'progress': status_details.get('layer')/print_data.get('layer_count')
                })
            return ret
    
    cmd_START_help = "Starts a new print with Odyssey"
    def cmd_START(self, gcmd):
        if self.printing:
            raise gcmd.error("Odyssey Busy")
        location = gcmd.get("LOCATION", default="Local")
        filename = gcmd.get("FILENAME")
        
        try:
            response = requests.post(f"{self.url}/print/start/{location}/{filename}")

            if response.status_code == requests.codes.not_found:
                raise gcmd.error("Odyssey could not find the requested file")
            elif response.status_code != requests.codes.ok:
                raise gcmd.error(f"Odyssey Error Encountered: {response.status_code}: {response.reason}")
            
            self.print_stats.set_current_file(f"{location}/{filename}")
            self.print_stats.note_start()
            self.reactor.update_timer(self.work_timer, self.reactor.NOW)
        except Exception as e:
            raise gcmd.error(f"Could not reach odyssey: {e}")


    
    cmd_CANCEL_help = "Cancels the currently running Odyssey print"
    def cmd_CANCEL(self, gcmd):
        try:
            response = requests.post(f"{self.url}/print/cancel")
            
            if response.status_code != requests.codes.ok:
                raise gcmd.error(f"Odyssey Error Encountered: {response.status_code}: {response.reason}")

            
            self.print_stats.note_cancel()
            self.printing = False
        except Exception as e:
            raise gcmd.error(f"Could not reach odyssey: {e}")


    cmd_PAUSE_help = "Pauses the currently running Odyssey print"
    def cmd_PAUSE(self, gcmd):
        try:
            response = requests.post(f"{self.url}/print/pause")
            if response.status_code != requests.codes.ok:
                raise gcmd.error(f"Odyssey Error Encountered: {response.status_code}: {response.reason}")

        except Exception as e:
            raise gcmd.error(f"Could not reach odyssey: {e}")


    cmd_RESUME_help = "Resumes the currently paused Odyssey print"
    def cmd_RESUME(self, gcmd):
        try:
            response = requests.post(f"{self.url}/print/resume")
            if response.status_code != requests.codes.ok:
                raise gcmd.error(f"Odyssey Error Encountered: {response.status_code}: {response.reason}")
            
            self.print_stats.note_start()
            self.reactor.update_timer(self.work_timer, self.reactor.NOW)
        except Exception as e:
            raise gcmd.error(f"Could not reach odyssey: {e}")

    
    def odyssey_work_tracker(self, eventtime):
        self.status = self.load_status()

        if self.printing:
            if "Idle" in self.status:
                self.print_stats.note_complete()
                self.printing = False
            elif "Printing" in self.status:
                if self.status['Printing']['paused']:
                    self.print_stats.note_pause()
                    self.printing = False
            return eventtime+1
        else:
            if "Printing" in self.status:
                if not self.status['Printing']['paused']:
                    self.printing = True
                    return eventtime+1

            return eventtime+10

def load_config(config):
    return Odyssey(config)
