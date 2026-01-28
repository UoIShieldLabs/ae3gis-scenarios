#include "beremiz.h"
#ifndef __POUS_H
#define __POUS_H

#include "accessor.h"
#include "iec_std_lib.h"

__DECLARE_ENUMERATED_TYPE(LOGLEVEL,
  LOGLEVEL__CRITICAL,
  LOGLEVEL__WARNING,
  LOGLEVEL__INFO,
  LOGLEVEL__DEBUG
)
// FUNCTION_BLOCK LOGGER
// Data part
typedef struct {
  // FB Interface - IN, OUT, IN_OUT variables
  __DECLARE_VAR(BOOL,EN)
  __DECLARE_VAR(BOOL,ENO)
  __DECLARE_VAR(BOOL,TRIG)
  __DECLARE_VAR(STRING,MSG)
  __DECLARE_VAR(LOGLEVEL,LEVEL)

  // FB private variables - TEMP, private and located variables
  __DECLARE_VAR(BOOL,TRIG0)

} LOGGER;

void LOGGER_init__(LOGGER *data__, BOOL retain);
// Code part
void LOGGER_body__(LOGGER *data__);
// PROGRAM MOTOR_CTRL
// Data part
typedef struct {
  // PROGRAM Interface - IN, OUT, IN_OUT variables

  // PROGRAM private variables - TEMP, private and located variables
  __DECLARE_VAR(BOOL,MOTOR_ERROR)
  __DECLARE_VAR(BOOL,MOTOR_ERROR_TRUE)
  __DECLARE_VAR(BOOL,RUN_MOTOR)
  __DECLARE_VAR(BOOL,MOTOR_RUNNING)
  __DECLARE_VAR(BOOL,STOP_MOTOR)
  __DECLARE_VAR(BOOL,RUN_MOTOR_TRUE)
  __DECLARE_VAR(BOOL,MOTOR_RUNNING_TRUE)
  __DECLARE_VAR(BOOL,STOP_MOTOR_TRUE)
  __DECLARE_VAR(INT,MOTOR_RPM)
  __DECLARE_VAR(INT,MOTOR_RPM_TRUE)
  __DECLARE_VAR(INT,TARGET_FREQ)
  __DECLARE_VAR(INT,TARGET_FREQ_TRUE)
  R_TRIG R_TRIG1;
  R_TRIG R_TRIG2;
  R_TRIG R_TRIG3;
  __DECLARE_VAR(INT,_TMP_SEL17_OUT)

} MOTOR_CTRL;

void MOTOR_CTRL_init__(MOTOR_CTRL *data__, BOOL retain);
// Code part
void MOTOR_CTRL_body__(MOTOR_CTRL *data__);
#endif //__POUS_H
