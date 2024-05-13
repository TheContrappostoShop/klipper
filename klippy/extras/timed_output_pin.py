from klippy.extras.output_pin import PrinterOutputPin


class TimedOutputPin:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.pin = PrinterOutputPin(config)
        self.reactor = self.printer.get_reactor()

        pin_name = config.get_name().split()[1]
        gcode = self.printer.lookup_object('gcode')
        gcode.register_mux_command("SET_PIN", "PIN", pin_name,
                                   self.cmd_SET_PIN,
                                   desc=self.cmd_SET_PIN_help)
    
    cmd_SET_PIN_TIMED_help = "Set the value of an output pin for the given time, and return the given response after the pin is reset"
    def cmd_SET_PIN_TIMED(self, gcmd):
        # Read requested value
        value = gcmd.get_float('VALUE', minval=0.0, maxval=self.scale)
        time = gcmd.get_float('TIME', minval=0.0)
        value /= self.scale
        if not self.is_pwm and value not in [0., 1.]:
            raise gcmd.error("Invalid pin value")
        
        self._pin_on(value)

        self.reactor.register_callback(lambda t: self._pin_off(gcmd), self.reactor.NOW+time)
    
    def _pin_off(self, gcmd):
        self.pin._set_pin(0, self.pin.shutdown_value)
        response = gcmd.get_string('RESPONSE', default=None)
        if response is not None:
            gcmd.respond_raw(response)

    def _pin_on(self, value):
        self.pin._set_pin(0, value)

def load_config(config):
    timed_output_pin = TimedOutputPin(config)
    config.get_printer().add_object('output_pin', timed_output_pin.get_pin())
    return timed_output_pin
