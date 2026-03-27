#include <SPI.h>
#include <mcp_can.h>

#define CAN_CS 10
#define CAN_INT 2
unsigned long lastPrint = 0;

// 🔥 LEFT MOTOR
#define IN1 5
#define IN2 6
#define ENA 9

// 🔥 RIGHT MOTOR
#define IN3 7
#define IN4 8
#define ENB 3   // PWM pin

MCP_CAN CAN(CAN_CS);

volatile bool flag = false;

// Interrupt function
void receiveInterrupt() {
  flag = true;
}

void setup() {
  Serial.begin(9600);

  pinMode(CAN_INT, INPUT);

  // 🔥 Motor pin setup
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(ENA, OUTPUT);

  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  pinMode(ENB, OUTPUT);

  // ❌ REMOVED: pinMode(53, OUTPUT); (Not needed for UNO)

  if (CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) == CAN_OK) {
    Serial.println("CAN Init OK");
  } else {
    Serial.println("CAN Init FAIL");
  }

  CAN.setMode(MCP_NORMAL);

  attachInterrupt(digitalPinToInterrupt(CAN_INT), receiveInterrupt, FALLING);
}



void loop() {
  if (!digitalRead(CAN_INT)) {

    unsigned long rxId;
    byte len;
    byte buf[8];

    while (CAN_MSGAVAIL == CAN.checkReceive()) {

      CAN.readMsgBuf(&rxId, &len, buf);

      int left_speed  = buf[0];
      int left_dir    = buf[1];
      int right_speed = buf[2];
      int right_dir   = buf[3];

      // MOTOR CONTROL
      analogWrite(ENA, left_speed);
      digitalWrite(IN1, left_dir == 1);
      digitalWrite(IN2, left_dir != 1);

      analogWrite(ENB, right_speed);
      digitalWrite(IN3, right_dir == 1);
      digitalWrite(IN4, right_dir != 1);

      // ✅ SAFE DEBUG (prints every 200ms only)
// ✅ SAFE DEBUG (every 200ms)
if (millis() - lastPrint > 200) {

  Serial.print("LEFT -> Speed: ");
  Serial.print(left_speed);
  Serial.print(" | Dir: ");
  Serial.print(left_dir == 1 ? "FWD" : "REV");

  Serial.print(" || RIGHT -> Speed: ");
  Serial.print(right_speed);
  Serial.print(" | Dir: ");
  Serial.println(right_dir == 1 ? "FWD" : "REV");

  lastPrint = millis();
}
    }
  }
}
