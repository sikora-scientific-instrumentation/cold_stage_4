#include <Adafruit_ADS1015-i2cmaster.h>
#include <Adafruit_MAX31865.h>


// Define device greeting parameters.
    const int NUM_CHANNELS = 1;
    const int UNIQUE_ID = 9;
    const char WELCOME_STRING[] = "30 MM Cold-stage";


// Instantiate ADS1115 ADC.
    Adafruit_ADS1115 ads;

    
// Prepare for setup of MAX31865 PRT digitisers.
    // CS pins for MAX31865s.
    const int MAX31865_CS_PINS[] = {A0, A1, A2, A3};
    // Create pointer array for MAX31865 objects.
    Adafruit_MAX31865 *prts[4];
    // The value of the Rref resistors. Use 430.0 for PT100 and 4300.0 for PT1000
    #define RREF      430.0
    // The 'nominal' 0-degrees-C resistance of the sensors
    // 100.0 for PT100, 1000.0 for PT1000
    #define RNOMINAL  100.0
    // NOTE - RREF on breakout board is a 430 ohm SMD component marked '4300'. A 4300 ohm component would be marked '4301'!


// Define PWM output pins.
    const uint8_t PWM_HOT = 5;
    const uint8_t PWM_COLD = 6;


// Message handling.
    const char command_strings[5][9] = {"Idle", "Throttle", "Channel", "Off", "Greeting"};
    const byte command_lengths[5] = {4, 8, 7, 3, 8};  
    const uint16_t MAX_INPUT = 36;
    char INPUT_BUFFER[MAX_INPUT];
    char CRC_BUFFER[4];
    uint16_t CRC_INDEX = 0;
    uint16_t INPUT_INDEX = 0;
    byte INPUT_MODE = 0;
    unsigned long COMMAND_DURATION_TIMEOUT = 100L;
    unsigned long COMMAND_SPACING_TIMEOUT = 1000L;
    unsigned long RESPONSE_TIMEOUT = 100L;
    unsigned long LAST_COMMS_START_TIMESTAMP = 0L;
    unsigned long LAST_COMMS_END_TIMESTAMP = 0L;
    unsigned long LAST_THROTTLE_TIMESTAMP = 0L;
    unsigned long THROTTLE_TIMEOUT_LIMIT = 2000L;
    

// Heartbeat LED.
    const uint8_t HEARTBEAT_PIN = 9;
    const unsigned long HEARTBEAT_SUPERFAST = 150L;
    const unsigned long HEARTBEAT_FAST = 250;
    const unsigned long HEARTBEAT_MEDIUM = 1000L;
    const unsigned long HEARTBEAT_SLOW = 3000L;
    unsigned long HEARTBEAT_DURATION = HEARTBEAT_SLOW;
    unsigned long HEARTBEAT_TIMESTAMP = 0L;
    bool HEARTBEAT_VALUE = false;


// Misc variables.
    const uint8_t RUNNING_PIN = 8;
    byte MODE = 6;
    uint8_t current_channel = 0;
    bool GREETING = false;
    unsigned long GREETING_START_TIMESTAMP = 0L;
    unsigned long GREETING_TIMESTAMP = 0L;
    unsigned long GREETING_DURATION = 2000L;
    float LAST_THROTTLE = 0.0;
    bool PELTIER_ACTIVE = false;


// Flowmeter bits.
    bool FLOW_CUTOUT = false;
    unsigned long FLOW_CHECK_TIMESTAMP = 0L;
    uint16_t FLOW_COUNTER = 0;
    float FLOW_RATE = 0.0;
    float LOW_FLOW_THRESHOLD = 1.0;


void setup () {
    // PWM bits.
        analogWrite(PWM_HOT, 0);
        analogWrite(PWM_COLD, 0);
        
        ads.begin();
        ads.setGain(GAIN_TWO);    // 2x gain   +/- 2.048V
    
    // Instantiate MAX31865 objects, initialise them and place references to them in the object pointer array.
        for (int i = 0; i < NUM_CHANNELS; i ++) {
            prts[i] = new Adafruit_MAX31865(MAX31865_CS_PINS[i]);
            prts[i]->begin(MAX31865_3WIRE);  // setup for 3 wire PRT100.
        }
        
    // Start UART and allow short delay.
        Serial.begin(57600);
        delay(500);

    // Misc.
        pinMode(HEARTBEAT_PIN, OUTPUT);
        digitalWrite(HEARTBEAT_PIN, HEARTBEAT_VALUE);
        pinMode(RUNNING_PIN, OUTPUT);
        digitalWrite(RUNNING_PIN, LOW);

        // Setup and start pinchange interrupt on A4 (see https://gammon.com.au/interrupts, towards the bottom of the page...).
        PCMSK1 |= bit (PCINT12);    // PCINT12 corresponds to A4.
        PCIFR |= bit (PCIF1);
        PCICR |= bit (PCIE1);
}


ISR (PCINT1_vect) {
    // Interrupt service routine called upon change at pin A4 (see https://gammon.com.au/interrupts, towards the bottom of the page...).
        FLOW_COUNTER ++;
}


void loop () {
    // Listen for any new incoming characters over serial connection, set new mode appropriately.
        bool message_to_process = serialListen(false, 0);
        byte new_mode = parseMessage(message_to_process);          // 0 = No change, 1 = Idle, 2 = Throttle, 3 = Switch channel, 4 = Shutdown off, 5 = Greeting...
    
    // Update device mode according to incoming message.
        applyCommand(new_mode);

    // Modulate heartbeat LED.
        heartBeat();

    // Check chiller flow.
        checkFlow();

    // Check throttle command timeout.
        checkThrottleTimeout();
}


void checkThrottleTimeout() {
    if (((millis() - LAST_THROTTLE_TIMESTAMP) > THROTTLE_TIMEOUT_LIMIT) && (PELTIER_ACTIVE == true)) {
        setThrottle(0.0);
        PELTIER_ACTIVE = false;
    }
}


void heartBeat() {
    // Handle heartbeat LED blinking.
        unsigned long timestamp = millis();
        if ((timestamp - LAST_COMMS_END_TIMESTAMP) > COMMAND_SPACING_TIMEOUT) {
            if (FLOW_RATE < LOW_FLOW_THRESHOLD) {
                HEARTBEAT_DURATION = HEARTBEAT_FAST;
            } else {
                HEARTBEAT_DURATION = HEARTBEAT_SLOW;
            }
        } else {
            if (FLOW_RATE < LOW_FLOW_THRESHOLD) {
                HEARTBEAT_DURATION = HEARTBEAT_FAST;
            } else {
                HEARTBEAT_DURATION = HEARTBEAT_MEDIUM;
            }
        }
        // Change heartbeat LED state if necessary...
        if (GREETING == false) {
            if (timestamp >= (HEARTBEAT_TIMESTAMP + HEARTBEAT_DURATION)) {
                // Toggle heartbeat LED...
                HEARTBEAT_VALUE = !HEARTBEAT_VALUE;
                digitalWrite(HEARTBEAT_PIN, HEARTBEAT_VALUE);
                HEARTBEAT_TIMESTAMP = timestamp;
            }
        } else {
            if (timestamp >= (GREETING_TIMESTAMP + HEARTBEAT_SUPERFAST)) {
                HEARTBEAT_VALUE = !HEARTBEAT_VALUE;
                digitalWrite(HEARTBEAT_PIN, HEARTBEAT_VALUE);
                digitalWrite(RUNNING_PIN, !HEARTBEAT_VALUE);
                GREETING_TIMESTAMP = timestamp;
                HEARTBEAT_TIMESTAMP = timestamp;
            }
            if (timestamp > (GREETING_START_TIMESTAMP + GREETING_DURATION)) {
                GREETING = false;
                digitalWrite(RUNNING_PIN, LOW);
            }
        }
}

void checkFlow() {
    // Check if the flow_detected flag has been set to true by the pinchange ISR since we last checked. If it hasn't, set the throttle
    // to zero immediately, and set the flow_cutout flag to true to hold the throttle at zero until flow is detected again.
        unsigned long timestamp = millis();
        if (timestamp >= (FLOW_CHECK_TIMESTAMP + 1000L)) {
            
            FLOW_RATE = ((float)FLOW_COUNTER) / 7.5;
            FLOW_COUNTER = 0;
            
            if ((FLOW_RATE < LOW_FLOW_THRESHOLD) && (PELTIER_ACTIVE == true)) {
                // Immediately set Peltier throttle to zero.
                setThrottle(0.0);
                PELTIER_ACTIVE = false;
                // Set flow cutout flag to true. Whenever setThrottle() is called with this flag asserted, throttle will be set to zero.
                FLOW_CUTOUT = true;
            } else {
                // Clear flow_cutout flag so throttle responds normally to commands.
                FLOW_CUTOUT = false;
            }
            FLOW_CHECK_TIMESTAMP = timestamp;
        }
}


bool serialListen(bool blocking, unsigned long timeout_msecs) {
        char character = ' ';
        bool crc_pass_flag = false;
        bool message_to_process = false;
        unsigned long start_time = millis(); 
        if (INPUT_MODE != 0) {
            if ((millis() - LAST_COMMS_START_TIMESTAMP) > COMMAND_DURATION_TIMEOUT) {
                INPUT_MODE = 0;
                INPUT_INDEX = 0;
                CRC_INDEX = 0;
            }
        }
        while (true) {
            while (Serial.available()) {
                character = Serial.read();
                if ((character == '>') && (INPUT_MODE == 0)) {
                    //Serial.println("INPUT STARTED...");
                    INPUT_MODE = 1;
                    INPUT_INDEX = 0;
                    LAST_COMMS_START_TIMESTAMP = millis();
                } else if ((character == '<') && (INPUT_MODE == 1)) {
                    //Serial.println("INPUT ENDED, CRC STARTED...");
                    INPUT_BUFFER[INPUT_INDEX] = char(0);
                    INPUT_MODE = 2;
                    CRC_INDEX = 0;
                } else if ((character == '<') && (INPUT_MODE == 2)) {
                    //Serial.println("CRC ENDED.");
                    CRC_BUFFER[CRC_INDEX] = char(0);
                    message_to_process = true;
                    INPUT_MODE = 0;
                    LAST_COMMS_END_TIMESTAMP = millis();
                    break;
                } else {
                    if (INPUT_MODE == 1) {
                      INPUT_BUFFER[INPUT_INDEX] = character;
                      INPUT_INDEX ++;
                      if (INPUT_INDEX >= MAX_INPUT) {
                          INPUT_MODE = 0;
                          INPUT_INDEX = 0;
                      }
                    } else if (INPUT_MODE == 2) {
                      CRC_BUFFER[CRC_INDEX] = character;
                      CRC_INDEX ++;
                      if (CRC_INDEX >= 4) {
                          INPUT_MODE = 0;
                          INPUT_INDEX = 0;
                          CRC_INDEX = 0;
                      }
                    }
                }
            }
            if (blocking == true) {
                //Serial.println("Blocking is true");
                if (message_to_process == true) {
                    //Serial.println("Message to process!");
                    break;
                } else {
                    if ((millis() - start_time) > timeout_msecs) {
                      //Serial.println("Timeout!");
                      INPUT_MODE = 0;
                      break;
                    }
                } 
            } else {
                break;
            }
        }
        if (message_to_process == true) {
            byte message_crc_value = CRC8((const byte*)INPUT_BUFFER, INPUT_INDEX);
            byte crc_check_value = atoi(CRC_BUFFER);
            crc_pass_flag = false;
            if (message_crc_value == crc_check_value) {
                crc_pass_flag = true;
            }
        }
        return crc_pass_flag;
}


void serialSpeak(const char *characters) {
    // Determine length of message.
    int message_length = 0;
    const char *starting_addr = characters;
    
    Serial.print('>');
    for (int n = 0; *characters != '\0'; characters ++) {
        Serial.print(*characters);
        message_length ++;
    }
    Serial.print('<');
    
    // Determine CRC value.
    byte crc_check_value = CRC8((const byte*)starting_addr, message_length);
    Serial.print(crc_check_value);
    Serial.print('<');
}


byte parseMessage(bool message_to_process){
    // Compare inbound message against available device commands and if any match, return new device mode.
        byte new_mode = 0;
        if (message_to_process == true) {
            for (int i = 0; i < 5; i ++) {
                if (strncmp(command_strings[i], INPUT_BUFFER, command_lengths[i]) == 0) {
                    new_mode = i + 1;
                }
            }
        } else {
            new_mode = 0;
        }
        return new_mode;
}


void applyCommand(byte new_mode) {
    // Change device behaviour to reflect most recent inbound command.
        switch (new_mode) {
            case 0:
                break;
            case 1:
                modeIdle();
                MODE = 1;
                break;
            case 2:
                modeThrottle();
                MODE = 2;
                break;
            case 3:
                modeChannel();
                MODE = 3;
                break;
            case 4:
                modeOff();
                MODE = 4;
                break;
            case 5:
                modeGreeting();
                MODE = 5;
                break;
        }
}


void modeIdle () {
    // Idle mode - Reply to master with current temperature - Both TC and PRT.
        static char output_buffer[10];
        serialSpeak(dtostrf(readThermocouple(current_channel), 7, 3, output_buffer));
        serialSpeak(dtostrf(readPRT(current_channel), 7, 3, output_buffer));
        serialSpeak(dtostrf(FLOW_RATE, 7, 3, output_buffer));
}


void modeThrottle() {
    // Throttle mode - Initial empty reply to acknowledge command, followed by blocking listen to receive new throttle setting.
    // Finally respond with current temperature - both TC and PRT.
        serialSpeak("*");
        bool ret = serialListen(true, RESPONSE_TIMEOUT);
        if (ret == true) {
          float throttle = atof(INPUT_BUFFER);
          setThrottle(throttle);
          PELTIER_ACTIVE = true;
          LAST_THROTTLE = throttle;
          static char output_buffer[10];
          serialSpeak(dtostrf(readThermocouple(current_channel), 7, 3, output_buffer));
          serialSpeak(dtostrf(readPRT(current_channel), 7, 3, output_buffer));
          serialSpeak(dtostrf(FLOW_RATE, 7, 3, output_buffer));
          LAST_THROTTLE_TIMESTAMP = millis();
        }
}


void modeChannel() {
    // Switch the current channel.
        // Initial empty acknowledgement of command.
        serialSpeak("*");
        // Listen for new channel number and switch if available.
        bool ret = serialListen(true, RESPONSE_TIMEOUT);
        if (ret == true) {
          uint8_t selected_channel = atoi(INPUT_BUFFER);
          if (selected_channel < NUM_CHANNELS) {
              current_channel = selected_channel;
          }
          // Acknowledge with channel number.
          char int_buffer[3];
          itoa(selected_channel, int_buffer, 10);
          int_buffer[1] = char(0);
          serialSpeak(int_buffer);
        }
}


void modeOff() {
    // Off mode - Set throttle to zero and acknowledge.
        serialSpeak("Off");
        setThrottle(0.0);
        PELTIER_ACTIVE = false;
}

void modeGreeting() {
    // Greeting mode - Reply with number of channels and start greeting heartbeat mode.
//        char int_buffer[3];
//        itoa(NUM_CHANNELS, int_buffer, 10);
//        serialSpeak(int_buffer);
        char serial_buffer[10];
        itoa(UNIQUE_ID, serial_buffer, 10);
        serialSpeak(serial_buffer);
        serialSpeak(WELCOME_STRING);
        itoa(NUM_CHANNELS, serial_buffer, 10);
        serialSpeak(serial_buffer);
        GREETING = true;
        GREETING_START_TIMESTAMP = millis();
        GREETING_TIMESTAMP = GREETING_START_TIMESTAMP;
        digitalWrite(HEARTBEAT_PIN, HIGH);
        digitalWrite(RUNNING_PIN, LOW);
}


void setThrottle(float throttle) {
    // Update hot and cold PWM channels to reflect new device throttle setting.
        if (FLOW_CUTOUT == false) {
            if (throttle > 0.0) {
                uint8_t pwm_cold_throttle = roundFloat(((float(255) / 100.0) * throttle));
                analogWrite(PWM_HOT, 0);
                analogWrite(PWM_COLD, pwm_cold_throttle);
                digitalWrite(RUNNING_PIN, HIGH);
            }
            if (throttle < 0.0) {
                uint8_t pwm_hot_throttle = roundFloat(((float(255) / 100.0) * (throttle * -1.0)));
                analogWrite(PWM_COLD, 0);
                analogWrite(PWM_HOT, pwm_hot_throttle);
                digitalWrite(RUNNING_PIN, HIGH);
            }
            if (throttle == 0.0) {
                analogWrite(PWM_HOT, 0);
                analogWrite(PWM_COLD, 0);
                digitalWrite(RUNNING_PIN, LOW);
            }
        } else {
            analogWrite(PWM_HOT, 0);
            analogWrite(PWM_COLD, 0);
            digitalWrite(RUNNING_PIN, LOW);
        }
}


uint16_t roundFloat(float floating) {
    // Round floating point to uint16_t.
        uint16_t integer_component = uint16_t(floating);
        float remainder = floating - float(integer_component);
        uint16_t integer;
        if (remainder >= 0.5) {
            integer = integer_component + 1;
        } else {
            integer = integer_component;
        }
        return integer;
}


float readThermocouple(uint8_t channel) {
    // Read thermocouple - Either ADS1115 digitising AD8495 analog thermocouple amplifier OR MAX31856 universal 
    // thermocouple amplifier and integrated digitiser.
        float temperature_degrees;
        int adc_reading = ads.readADC_SingleEnded(channel);
        float volts_per_bit = 0.0625;
        float voltage = (adc_reading * volts_per_bit) / 1000.0;
        temperature_degrees = (voltage - 1.25) / 0.005;
        return temperature_degrees;
}


float readPRT(uint8_t channel) {
    // Read MAX31865 PRT digitiser.
        uint16_t prt_reading = prts[channel]->readRTD();                          // Obtain raw reading from PRT digitiser.
        float prt_temperature = prts[channel]->temperature(RNOMINAL, RREF);      // Convert this to decimal temperature.
        return prt_temperature;
}


//CRC-8 - based on the CRC8 formulas by Dallas/Maxim
//code released under the therms of the GNU GPL 3.0 license
byte CRC8(const byte *data, byte len) {
  byte crc = 0x00;
  while (len--) {
    byte extract = *data++;
    for (byte tempI = 8; tempI; tempI--) {
      byte sum = (crc ^ extract) & 0x01;
      crc >>= 1;
      if (sum) {
        crc ^= 0x8C;
      }
      extract >>= 1;
    }
  }
  return crc;
}
