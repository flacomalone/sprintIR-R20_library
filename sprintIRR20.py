# AUTHOR: DAVID TENA GAGO

import time
import struct
import arguments_values_helpers as hp
import machine
import math
from machine import UART

class SprintIRR20_timeout(Exception):
     def __init__(self, message="Timeout error obtained when interacting with SprintIRR20 sensor"):
        self.message = message
        super().__init__(self.message)

class SprintIRR20_unexpected_reply(Exception):
     def __init__(self, message="Unexpected message obtained when interacting with SprintIRR20 Sensor"):
        self.message = message
        super().__init__(self.message)

class SprintIRR20_connection_lost(Exception):
     def __init__(self, message="Communication lost when interacting with SprintIRR20 Sensor"):
        self.message = message
        super().__init__(self.message)

class sprintIRR20:
    def __init__(self, verbose=False, verbose_measuring=False, timeout=1, scaling_factor=None):
        self.uart = UART(1, baudrate=38400, bits=8, parity=None, stop=1, pins=('P2','P10'), timeout_chars=1200) #1s timeout. Pins(Tx, Rx)
        self.verbose = verbose
        self.verbose_measuring = verbose_measuring

        time.sleep(1) # This is needed. Otherwise, sensor won't be able to read after reboot
        if self.verbose:
            print("\nPlease wait for CO2 sensor startup...")

        self.timeout = timeout # seconds
        if scaling_factor is None:
            self.scalingFactor = self.getScalingFactorMultiplier()
        else:
            self.scalingFactor = scaling_factor
        self.compensationValue = self.getPressureAndCompensationValue()
        self.pressure = self.compensationToPressure(self.compensationValue)
        self.digitalFilter = self.getDigitalFilter()
        if self.verbose:
            print("\n----------- START OF SENSOR START-UP INFORMATION -----------")
            print("SprintIRR20 -> Scaling multiplier factor: ", self.scalingFactor)
            print("SprintIRR20 -> Concentration compensation value: ", self.compensationValue, ", meaning that the sensor is intended to work at ", self.pressure, " mbar of pressure")
            print("SprintIRR20 -> Digital filter: ", self.digitalFilter)
            firmware, serial = self.getFirmwareAndSerial()
            print("SprintIRR20 -> Firmware: ", firmware)
            print("SprintIRR20 -> Serial number: ", serial)
            print("----------- END OF SENSOR START-UP INFORMATION -----------\n")


########################### MEASUREMENTS ###########################

# The most important factor is the gas exchange rate.  This is the amount of time it takes for the gas to
# enter the CO2 measurement chamber, measured and then replaced.  The sensor has a gas
# measurement chamber volume of approximately 2.8ml.  As a general rule of thumb, to properly
# exchange the gas in the chamber, there needs to be a x5 volume of gas passed through the sensor.
# Therefore, approximately 14ml of gas needs to flow through the sensor for each reading. Thus, max flow rate is 42 litres/minute

# The sensor outputs both filtered and raw unfiltered CO2 readings. If the filtered measurement data is
# used, the read rate will also depend on the filter setting or the algorithm to process the raw data. Increasing the filter setting
# increases the measurement output response time. Sampling noise is progressively reduced with higher digital filter settings. It is recommended the
# user sets the highest value digital filter setting without compromising the required flow rate. For example:

# Flow rate (litre/minute) | recommended digital filter setting
# --------------------------------------------------------------
#  0.1                     | 128 (recommended)
#  0.5                     | 64
#  1                       | 32
#  5                       | 16 (the sensor uses this one by default)


    def getCO2Measurement(self, filtered=False, check_correction=True):
        if filtered:
            value = self.getMostRecentFilteredCO2Measurement()
        else:
            value = self.getMostRecentUnfilteredCO2Measurement()

        if value < 0 or type(value) != int: #To prevent CO2 agent from collapsing after treating occasional negative values
            return -1
        else:
            value = value * self.scalingFactor

        if check_correction and self.PPMtoPercentage(value) > 1.0: # Concentration > 1.0 %
                return self.correctMeasurement(value)
        else:
            return value


    # Return the most recent filtered CO2 measurement in ppm
    # This value needs to be multiplied by the appropriate scaling factor to derive the ppm value.
    def getMostRecentFilteredCO2Measurement(self):
        self.uart.write("Z\r\n")
        result = self.UART_recv(timeout=self.timeout)
        if result is None:
            print("ERROR received when executing command getMostRecentFilteredCO2Measurement")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose and self.verbose_measuring:
                print("getMostRecentFilteredCO2Measurement response: ", result)
            return int(float(result[3:8]))

    # Return the most recent unfiltered CO2 measurement in ppm
    # This value needs to be multiplied by the appropriate scaling factor to derive the ppm value.
    def getMostRecentUnfilteredCO2Measurement(self):
        self.uart.write("z\r\n")
        result = self.UART_recv(timeout=self.timeout)
        if result is None:
            print("ERROR received when executing command getMostRecentUnfilteredCO2Measurement")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose and self.verbose_measuring:
                print("getMostRecentUnfilteredCO2Measurement response: ", result)
            return int(float(result[3:8]))

    def PPMtoPercentage(self, value):
        if value is None or value < 0:
            print("ERROR: value must be positive")
            return -1

        return float("{:.2f}".format(value / 10000))

    # Correction made for concentrations > 1%
    def correctMeasurement(self, value):
        if value >= 1500:
            Y = 2.6661 * math.pow(10,-16) * math.pow(value,4) - 1.1146 * math.pow(10,-12) * math.pow(value,3) + 1.7397 * math.pow(10,-9) * math.pow(value,2) - 1.2556 * math.pow(10,-6) * value - 9.8754 * math.pow(10,-4)
        else:
            Y = 2.881 * math.pow(10,-38) * math.pow(value,6) - 9.817 * math.pow(10,-32) * math.pow(value,5) + 1.304 * math.pow(10,-25) * math.pow(value,4) - 8.126 * math.pow(10,-20) * math.pow(value,3) + 2.311 * math.pow(10,-14) * math.pow(value,2) - 2.195 * math.pow(10,-9) * value - 1.471 * math.pow(10,-3)

        value_after = int(value / (1 + Y * (1013 - self.pressure)))
        print("before:", str(value), ", after:", str(value_after))
        return value_after

########################### DIGITAL FILTERS SETTINGS ###########################
#The CO₂ measurement is passed through a digital filter to condition the signal. The characteristics of
#the filter can be altered by the user to tune the sensor performance to specific applications.
#The filter operates as a low pass filter; increasing the filter parameter reduces measurement noise,
#but slows the response. There is a trade-off between noise (resolution) and speed of response.
#The filter can be set to a value between 1 and 65535 although settings higher than 64 are not
#recommended for normal use. A low value will result in the fastest response to changes in gas
#concentration, a high value will result in a slower response.

#Increasing the filter setting has a beneficial impact on noise, so improves the sensor resolution. It
#also slows the sensor response to transients. This can be used to improve the detection of average
#CO₂ conditions. In building control, for example, a fast response to breathing near the sensor is
#undesirable. If the transient response is important either for speed of response or because the shape
#of the transient is required, a low filter setting should be used

#To improve zeroing accuracy, the recommended digital filter setting is 32.

#IMPORTANT: the sensor keeps after reboot the latest digital filter set

    # Return the value of the digital filter. Range must be between 1 and 65635
    def setDigitalFilter(self, value):
        if value is None or value > 65635 or not hp.positive(value) or value == 0:
            print("ERROR: value must be set between 0 and 65635")
            return -1

        value_str = hp.formatArgument5digits(value)
        command = "A " + value_str + "\r\n"
        self.uart.write(command)
        result = self.UART_recv(timeout=self.timeout)[1:].decode()
        if result != command:
            print("ERROR received when executing command setDigitalFilter")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                print("Set digital filter command has just been sent with response: ", result)
            return 0

    # Return the value of the digital filter
    def getDigitalFilter(self):
        self.uart.write("a\r\n")
        result = self.UART_recv(timeout=self.timeout)[3:8]
        if result is None:
            print("ERROR received when executing command getDigitalFilter")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                print("Get digital filter command has just been sent with result: ", result)
            return int(result)

########################### ZERO-POINT SETTINGS ###########################
# There are a several methods available to the user to set the zero point of the sensor.  The
# recommended user method is zero-point setting in a known gas concentration.  In all cases, the best
# zero is obtained when the gas concentration is stable, and the sensor is at an established temperature.

# Note that zero-point settings are not cumulative and only the latest zero-point is effective. For
# example, there is no benefit in zeroing in nitrogen, and then zeroing in a calibration gas.  The sensor
# will store only the latest zero point.


    # If the CO2 concentration and the sensor reported concentration are known (both in PPM), the zero point can be
    # adjusted using the known concentration to fine tune the zero point.  For example, if the sensor has
    # been in an environment that has been exposed to outside air, and the sensor reading is known at
    # that time, the zero point can be fine-tuned to correct the reading.  This is typically used to
    # implement automated zeroing routines.  The first parameter is the reading reported
    # by the sensor. The second is the corrected reading.
    def fineTuneZeroPoint(self, known_reading, known_concentration):
        if known_reading is None or not hp.positive(known_reading) or known_reading is None or not hp.positive(known_reading):
            print("ERROR: values must be positive")
            return -1

        known_reading = int(known_reading / self.scalingFactor)
        known_concentration = int(known_concentration / self.scalingFactor)
        command = "F " + str(known_reading) + " " + str(known_concentration) + "\r\n"
        self.uart.write(command)
        result = self.UART_recv(timeout=self.timeout)[1:].decode()
        if result is None: # responded with multiple values
            print("ERROR received when executing command fineTuneZeroPoint")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                print("Fine tune zero point command has just been sent with knownReading = ", known_reading, " and KnownConcentration = ", known_concentration, ". Response: ", result)
            return 0

    # Zero-point setting using fresh air.
    # The concentration value written to the sensor must be scaled dependent on the sensor CO2 measurement range.
    # The sensor can use the default fresh air CO2 concentration value (400ppm), or the user can write a different fresh air value to the sensor if desired (P command).
    def zeroPointFreshAir(self):
        self.uart.write("G\r\n")
        result = self.UART_recv(timeout=self.timeout)[1:].decode()
        if result is None:
            print("ERROR received when executing command zeroPointFreshAir")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                print("Zero point using fresh air command has just been sent with response: ", result)
            return 0

    # Zero-point setting using nitrogen assuming the sensor is in a 0 CO2 ppm environment
    def zeroPointNitrogen(self):
        self.uart.write("U\r\n")
        result = self.UART_recv(timeout=self.timeout)[1:].decode()
        if result is None: # Responded with G 32662
            print("ERROR received when executing command zeroPointNitrogen")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                print("Zero point using nitrogen command has just been sent")
            return 0

    # Forces a specific zero set point value. Input value is scaled by CO2 value multiplier
    def zeroPointManualSetting(self, value):
        if value is None or not hp.positive(value):
            print("ERROR: value must be positive")
            return -1
        value = value/self.scalingFactor
        value_str = hp.formatArgument5digits(value)
        command = "u " + value_str + "\r\n"
        self.uart.write(command)
        result = self.UART_recv(timeout=self.timeout)[1:].decode()
        if result != command:
            print("ERROR received when executing command zeroPointManualSetting")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                print("Zero point using manual setting command has just been sent")
            return 0

    # Sets the zero point with the sensor in a known concentration of CO2. Input value is scaled by CO2 value multiplier
    def zeroPointKnownGas(self, value):
        if value is None or not hp.positive(value):
            print("ERROR: value must be positive")
            return -1

        value = value/self.scalingFactor
        value_str = hp.formatArgument5digits(value)
        command = "X " + value_str + "\r\n"
        self.uart.write(command)
        result = self.UART_recv(timeout=self.timeout)[1:].decode() # responded with X 35548
        if result == None:
            print("ERROR received when executing command zeroPointKnownGas")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                print("Zero point known gas command has just been sent")
            return 0

########################### CONCENTRATION BACKGROUND SETTINGS ###########################

# When a value has to be introduced as a two-byte word, MSB comes first and then LSB. The next line gives an example:
#Example: convert 400 to two-byte word:
    # MSB = Integer(400/256)
    # LSB = 400 - (256*MSB)

    # Sets value of CO2 background concentration in ppm for auto-zeroing. Input value is scaled by CO2 value multiplier
    def setBackgroundPPMAutozeroing(self, value):
        if value is None or not hp.positive(value):
            print("ERROR: value must be positive")
            return -1

        value = value/self.scalingFactor
        msb = int(value/256)
        lsb = int(value - (256*msb))
        msb_str = hp.formatArgument5digits(msb)
        lsb_str = hp.formatArgument5digits(lsb)

        command_msb = "P 00008 " + msb_str + "\r\n"
        command_lsb = "P 00009 " + lsb_str + "\r\n"

        self.uart.write(command_msb)
        result_msb = self.UART_recv(timeout=self.timeout)[1:].decode()
        if result_msb != command_msb:
            print("ERROR received when executing command setBackgroundPPMAutozeroing")
            raise SprintIRR20_unexpected_reply()
        else:
            self.uart.write(command_lsb)
            result_lsb = self.UART_recv(timeout=self.timeout)[9:14].decode()
            if result_lsb != command_lsb:
                print("ERROR received when executing command setBackgroundPPMAutozeroing")
                raise SprintIRR20_unexpected_reply()
            else:
                if self.verbose:
                    print("Background for auto-zeroing command has just been sent with response: ", result_msb[:-2], " ", result_lsb[:-2])
                return 0


    # Sets value of CO2 background concentration in ppm used for zero-point setting in fresh air. Input value is scaled by CO2 value multiplier
    def setBackgroundPPMFreshAir(self, value):
        if value is None or not hp.positive(value):
            print("ERROR: value must be positive")
            return -1

        value = value/self.scalingFactor
        msb = int(value/256)
        lsb = int(value - (256*msb))
        msb_str = hp.formatArgument5digits(msb)
        lsb_str = hp.formatArgument5digits(lsb)

        command_msb = "P 00010 " + msb_str + "\r\n"
        command_lsb = "P 00011 " + lsb_str + "\r\n"

        self.uart.write(command_msb)
        result_msb = self.UART_recv(timeout=self.timeout)[1:].decode()
        if result_msb != command_msb:
            print("ERROR received when executing command setBackgroundPPMFreshAir")
            raise SprintIRR20_unexpected_reply()
        else:
            self.uart.write(command_lsb)
            result_lsb = self.UART_recv(timeout=self.timeout)[1:].decode()
            if result_lsb != command_lsb:
                print("ERROR received when executing command setBackgroundPPMFreshAir")
                raise SprintIRR20_unexpected_reply()
            else:
                if self.verbose:
                    print("Background for auto-zeroing in fresh air command has just been sent with response: ", result_msb[:-2], " ", result_lsb[:-2])
                return 0

########################### MODE SETTINGS ###########################
# MODE 0 COMMAND MODE
# This is primarily intended for use when extracting larger chunks of information from the sensor (for example using the Y and * commands).
# In this mode, the sensor is in a SLEEP mode, waiting for commands.  No measurements are made.
# There is no latency in command responses.  All commands that report measurements or alter the
# zero-point settings are disabled in Mode 0.  Mode 0 is NOT retained after power cycling.
# IMPORTANT: Commands which report measurements or alter the zero point setting are disabled in mode 0.

# MODE 1 STREAMING MODE
# This is the factory default setting.  Measurements are reported 50 per second.  Commands are
# processed when received, except during measurement activity, so there may be a time delay of up
# to 10ms in responding to commands.

# MODE 2 POLLING MODE (USE THIS ONE)
# In polling mode, the sensor only reports readings when requested.  The sensor will continue to take
# measurements in the background, but the output stream is suppressed until data is requested.  The
# sensor will always power up in streaming or polling mode, whichever mode was used before the
# power cycle.

# Note that the sensor will power up in the mode last used.  If it was last used in K0 mode, it will power up
# in either K1 or K2 mode, depending on which was most recently used.

    # Switch operation mode from command (0), streaming (1) and polling (2)
    def switchMode(self, mode):
        if mode in [0,1,2]:
            command = "K 0000" + str(mode) + "\r\n"
            self.uart.write(command)
            result = self.UART_recv(timeout=self.timeout)[1:].decode()
            if result != command:
                print("ERROR received when executing command switchMode")
                raise SprintIRR20_unexpected_reply()
            else:
                if self.verbose:
                    print("Mode switched to " + str(mode))
                return 0
        else:
            print("ERROR: mode must be between 0 and 2")
            return -1

########################### OUTPUT FORMAT SETTINGS ###########################

    #Sets the number of measurement data types output by the sensor
    def setNumberMeasurementsDataTypesOutput(self, value):
        pass

    # Reports the latest measurement data types, as defined by ‘M’
    def getLatestMeasurementDataTypes(self):
        pass

########################### PRESSURE AND CONCENTRATION COMPENSATION SETTINGS ###########################
# In general, as the pressure increases, the reported gas concentration also increases. As the pressure decreases, the reported
# concentration decreases.  This effect takes place at a molecular level and is common to all NDIR gas
# sensors. The sensors are calibrated at 1013 mbar and 450ppm CO2. It is possible to correct for the effects of pressure and concentration by setting a
# compensation value.  This will apply a permanent correction to the output of the sensor, depending
# on the compensation value.

# For CO2 concentrations above 1%, a higher accuracy compensation formula needs to be used.

    def altitudeToPressure(self, altitude):
        if altitude != None and altitude > 0:
            return 1013.25 * math.pow((1-0.0000225577 * altitude),5.25)
        else:
            print("ERROR: value must be positive")
            return -1

    def pressureToCompensation(self, pressure): # Pressure in mbar
        return int(8192 + ((1013 - pressure) * 0.14 / 100) * 8192)


    def compensationToPressure(self, compensation):
        return int((((compensation - 8192) * 100)/8192 - (1013*0.14)/0.14) * -1)


    # Sets the pressure and concentration compensation value
    def setPressureAndCompensationValue(self, value):
        if value is None or not hp.positive(value):
            print("ERROR: value must be positive")
            return -1

        value_str = hp.formatArgument5digits(value)
        command = "S " + value_str + "\r\n"
        self.uart.write(command)
        result = self.UART_recv(timeout=self.timeout)[1:].decode()
        if result != command:
            print("ERROR received when executing command setPressureAndCompensationValue")
            raise SprintIRR20_unexpected_reply()
        else:
            self.compensationValue = int(value)
            if self.verbose:
                print("Set compensation value command has just been sent")
            return 0

    # Returns the pressure and concentration compensation value
    def getPressureAndCompensationValue(self):
        command = "s\r\n"
        self.uart.write(command)
        result = self.UART_recv(timeout=self.timeout)[3:8].decode()
        if result is None or int(result) < 0:
            print("ERROR received when executing command getPressureAndCompensatioValue")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                print("Get compensation value command has just been sent")
            return int(result)

########################### AUTO-ZEROING SETTINGS ###########################
# The sensor has a built-in auto-zero function.  In order to function correctly, the sensor must be
# exposed to typical background levels (400-450ppm) at least once during the auto-zero period.  For
# example, many buildings will drop quickly to background CO2 levels when unoccupied overnight or at
# weekends.  The auto-zero function uses the information gathered during these periods to re-zero.
# The sensor will reset the ‘zero’ level every time it does an auto-zero. Auto-zero is disabled by
# default. If the sensor is powered down, the auto-zero is reset to default values.


# IMPORTANT: to change the auto-zeroing configuration, the sensor must set first to mode 0

    # Sets the timing for initial and interval auto-zeroing periods.
    # The auto-zero period can be set independently of the start-up auto-zero time. Note, the zero settings are reset if the sensor is powered down.
    # Both the initial interval and regular interval are given in days. Both must be entered with a decimal point and one figure after the decimal point.
    # Example: "@ 1.0 8.0\r\n" the auto-zero regular interval is set to 8 days, and the initial interval set to 1 day
    def setInitialAndIntervalAutoZeroing(self, initial, regular):
        if initial is None or not hp.positive(initial) or regular is None or not hp.positive(regular):
            print("ERROR: values must be positive")
            return -1

        elif hp.numberOfDigits(initial) > 1 or hp.numberOfDigits(regular) > 1:
            print("ERROR: values must be set between 0 and 9")
            return -1

        command = "@ " + str(initial) + ".0 " + str(regular) + ".0\r\n"
        self.uart.write(command)
        result = self.UART_recv(timeout=self.timeout)[1:].decode()
        if result != command:
            print("ERROR received when executing command setInitialAndIntervalAutoZeroing")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                print("Set auto zeroing interval values command has just been sent")
            return 0

    # Returns the auto-zeroing configuration.
    # DOES NOT RETURN DUE VALUES
    def getAutoZeroingConfiguration(self):
        command = "@ \r\n"
        self.uart.write(command)
        result = self.UART_recv(timeout=self.timeout)[1:].decode()
        if result is None:
            print("ERROR received when executing command getAutoZeroingConfiguration")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                if result == "@ 0\r\n":
                    print("Auto-zeroing is disabled and there is no configuration")
                else:
                    print("Auto-zeroing configuration: ", result)
            return 0


    # Switch Auto-zeroing on or off. Default is off.
    def switchAutoZeroing(self, value=True):
        if value:
            command = "@ 1\r\n"
        else:
            command = "@ 0\r\n"

        self.uart.write(command)
        result = self.UART_recv(timeout=self.timeout)[1:].decode()
        if result != command:
            print("ERROR received whem executing command SwitchAutoZeroing")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                if value:
                    print("Auto-zering has just been enabled")
                else:
                    print("Auto-zering has just been disabled")
            return 0

########################### MISC. ###########################

    # Returns the scaling factor multiplier required to convert the Z or z output to ppm
    # The multiplier must also be used when sending CO2 concentration levels to the sensor, for example when setting the fresh air CO2 concentration value.
    def getScalingFactorMultiplier(self):
        self.uart.write(".\r\n")
        result = self.UART_recv(timeout=self.timeout)[3:8].decode()
        if result is None:
            print("ERROR received when executing command getScalingFactorMultiplier")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                print("Get scaling factor command has just been sent with response: ", result)
            return int(result)

    # Return firmware version and sensor serial number
    # Example:
        # Y,Aug 25 2021,14:19:56 - > firmware compile date and time LP15132 -> firmware version
        # B 528148 -> serial number, 00000
    def getFirmwareAndSerial(self):
        self.uart.write("Y\r\n")
        firmware = self.UART_recv(timeout=self.timeout).decode()
        serial = self.UART_recv(timeout=self.timeout).decode()
        if firmware is None or serial is None:
            print("ERROR received when executing command getFirmwareAndSerial")
            raise SprintIRR20_unexpected_reply()
        else:
            if self.verbose:
                print("Get firmware and serial information command has just been sent")
            return firmware, serial

    def getMessageType(self):
        return self.UART_recv(timeout=self.timeout)[1:2].decode()

    def UART_recv(self, timeout=0):
        counter = 0
        if timeout != 0: # Timeout specified
            timeout_iters = 16 * timeout # aprox rate is 16 reads per second, so multiply seconds by 16 to establish timeout
            for counter in range(timeout_iters):
                response = self.uart.readline()
                if response is None:
                    continue
                else:
                    # Uncomment this code if you want to reset mode 0 because of messages flooding
                    # if self.getMessageType() != "K":
                    #     continue
                    break
            if response is None:
                raise SprintIRR20_timeout()
            return response

        else: # No timeout
            while True:
                response = self.uart.readline()
                if response is None:
                    counter += 1
                    print(counter)
                    continue
                else:
                    # Uncomment this code if you want to reset mode 0 because of messages flooding
                    # if self.getMessageType() != "K":
                    #     continue
                    break
            return response
