#if __has_include(<Arduino.h>)
  #include <Arduino.h>
#elif __has_include("Arduino.h")
  #include "Arduino.h"
#else
  // The project is intended for an Arduino/ESP device and requires the
  // platform SDK include path to be configured in the build environment.
  #include <cstddef>
  #include <cstdint>
  #define IR_REMOTE_VERIFICATION_NO_ARDUINO
#endif

#if !defined(IR_REMOTE_VERIFICATION_NO_ARDUINO)
  // The user's captured remote frames used NEC. This receiver-only test has no
  // motor pins, motor commands, or movement behavior.
  #define DECODE_NEC
  #include <IRremote.hpp>
  #include "sg555_keymap.h"
#endif

#if !defined(IR_REMOTE_VERIFICATION_NO_ARDUINO)
  // Match the Arduino Uno IR signal input used by the verified test wiring.
  constexpr uint8_t IR_RECEIVE_PIN = A1;
  constexpr uint32_t SERIAL_BAUD = 115200UL;

  const char *findButtonLabel ( uint16_t address, uint16_t command )
  {
    for ( size_t index = 0; index < SG555_KEY_COUNT; ++index )
    {
      if ( SG555_KEYS[index].address == address && SG555_KEYS[index].command == command )
      {
        return SG555_KEYS[index].label;
      }
    }

    return nullptr;
  }

  void printHexValue ( uint32_t value, uint8_t digits )
  {
    static const char HEX_DIGITS[] = "0123456789ABCDEF";

    for ( int8_t shift = static_cast<int8_t> ( ( digits - 1 ) * 4 ); shift >= 0; shift -= 4 )
    {
      Serial.print ( HEX_DIGITS[( value >> shift ) & 0x0F] );
    }
  }

  void printDecodedFrame ( const IRData &data )
  {
    Serial.print ( F ( "IR;protocol=" ) );
    Serial.print ( getProtocolString ( data.protocol ) );
    Serial.print ( F ( ";address=0x" ) );
    printHexValue ( data.address, data.address > 0xFF ? 4 : 2 );
    Serial.print ( F ( ";command=0x" ) );
    printHexValue ( data.command, data.command > 0xFF ? 4 : 2 );
    Serial.print ( F ( ";raw=0x" ) );
    printHexValue ( data.decodedRawData, 8 );
    Serial.print ( F ( ";bits=" ) );
    Serial.print ( data.numberOfBits );

    const char *buttonLabel = findButtonLabel ( data.address, data.command );
    if ( buttonLabel != nullptr )
    {
      Serial.print ( F ( ";button=" ) );
      Serial.print ( buttonLabel );
      Serial.print ( F ( ";map_status=LEARNED" ) );
    }
    else
    {
      Serial.print ( F ( ";button=UNMAPPED" ) );
      Serial.print ( F ( ";map_status=NO_LEARNED_ENTRY" ) );
    }

    Serial.println ( );
  }

  void setup ( )
  {
    Serial.begin ( SERIAL_BAUD );
    IrReceiver.begin ( IR_RECEIVE_PIN, DISABLE_LED_FEEDBACK );

    Serial.println ( );
    Serial.println ( F ( "IR_TEST_READY;board=ARDUINO_UNO;receiver_pin=A1;baud=115200" ) );
    Serial.println ( F ( "MOTION=DISABLED;SERIAL_OUTPUT_ONLY=1" ) );
    Serial.print ( F ( "LEARNED_BUTTONS=" ) );
    Serial.println ( SG555_KEY_COUNT );
  }

  void loop ( )
  {
    if ( IrReceiver.decode ( ) )
    {
      const IRData &data = IrReceiver.decodedIRData;
      const bool isRepeat = ( data.flags & IRDATA_FLAGS_IS_REPEAT ) != 0;

      // Do not flood the monitor when a key is held; log its initial frame only.
      if ( !isRepeat && data.protocol != UNKNOWN )
      {
        printDecodedFrame ( data );
      }
      else if ( !isRepeat )
      {
        Serial.println ( F ( "IR;protocol=UNKNOWN;button=UNMAPPED;map_status=PROTOCOL_NOT_DECODED" ) );
      }

      IrReceiver.resume ( );
    }
  }
#endif

#if defined(IR_REMOTE_VERIFICATION_NO_ARDUINO)
int main ( )
{
  return 0;
}
#endif
