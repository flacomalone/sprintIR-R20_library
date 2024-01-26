AUTHOR: DAVID TENA GAGO

This repo is intended to provide a library to interface with a SprintIR - R20 CO2 sensor, from www.co2meter.com.

The specific details and documentation about this sensor can be seen at the [manufacturers site](https://www.co2meter.com/en-es/products/sprintir-r-20-co2-sensor). 

The library is written in MicroPython, and includes the following operations:
- setDigitalFilter (A): Set value of the digital filter
- getDigitalFilter (a): Set the value for the digital filter
- fineTuneZeroPoint (F):Fine Tune the zero point
- zeroPointFreshAir (G): Zero-point setting using fresh air. Command setParameterValue (P) must be set first, otherwise calibration won't be good
- switchMode (K): Switches the sensor between different modes
- setNumberMeasurementsDataTypesOutput (M): Sets the number of measurement data types output by the sensor
- setParameterValue (P): Sets value of CO2 background concentration in ppm for auto-zeroing. Input value is scaled by CO2 value multiplier, see ‘.’ command
- getLatestMeasurementDataTypes (Q): Reports the latest measurement data types, as defined by ‘M’
- setPressureAndConcentrationValue (S): Set the ‘Pressure and Concentration Compensation' value
- getPressureAndConcentrationValue (s): Returns the pressure and concentration compensation value
- zeroPointNitrogen (U): Sets the zero point assuming the sensor is in 0ppm CO2 such as nitrogen.
- zeroPointManualSetting (u): Forces a specific zero set point value. Input value is scaled by CO2 value multiplier, see ‘.’ command. User guide recommends not to use it without their counseling
- zeroPointKnownGas (X): Zero-point setting using a known gas calibration
- getFirmwareAndSerial (Y): Return firmware version and sensor serial number
- getMostRecentFilteredCO2Measurement (Z): Return the most recent filtered CO2 measurement in ppm
- getMostRecentUnfilteredCO2Measurement (z): Return the most recent unfiltered CO2 measurement in ppm
- autoZeroingConfiguration (@): Sets the timing for initial and interval auto-zeroing periods
- getScalingFactorMultiplier (.): Returns the scaling factor multiplier required to convert the Z or z output to ppm

More information about each of the operation can be found in [this link](https://www.gassensing.co.uk/wp-content/uploads/2023/05/SprintIR-R-Data-Sheet-Rev-4.12_3.pdf).

## Digital filter
The sensor outputs both filtered and raw unfiltered CO2 readings. If the filtered measurement data is used, the read rate will also depend on the filter setting or the algorithm to process the raw data

The CO2 gas chamber is illuminated with a nominal 4.25um wavelength LED and the signal received using a photo-diode. The signal from the photo-diode is processed and filtered by the sensor to remove noise and provide an accurate CO2 reading. High frequency noise coming from the sampling process is removed using a proprietary lowpass filter. The digital filter setting can be varied, allowing the user to reduce measurement noise at the expense of the measurement response time.

The ideal digital filter setting is application specific and is normally a balance between CO2 reading accuracy and response time. The SprintIR®-R sensor will also output the raw unfiltered CO2 measurement data. This data can be post processed using alternative filter algorithms.

| Flow Rate       | Recommended Digital Filter Setting |
|-----------------|------------------------------------|
| 0.1litre/minute | 128                                |
| 0.5litre/minute | 64                                 |
| 1litre/minute   | 32                                 |
| 5litre/minute   | 16                                 |

## Usage
```python
from sprintIRR20 import sprintIRR20, SprintIRR20_timeout, SprintIRR20_connection_lost

co2_sensor = sprintIRR20(verbose=True, timeout=5)
co2_sensor.setDigitalFilter(64)
while 1:
    concentration = co2_sensor.getCO2Measurement(filtered=True, check_correction=False)
    print("CONCENTRATION: ", concentration, "\tPPM (", co2_sensor.PPMtoPercentage(concentration), "\t%)")
```
