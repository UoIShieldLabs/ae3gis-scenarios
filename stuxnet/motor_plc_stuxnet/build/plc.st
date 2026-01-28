TYPE
  LOGLEVEL : (CRITICAL, WARNING, INFO, DEBUG) := INFO;
END_TYPE

FUNCTION_BLOCK LOGGER
  VAR_INPUT
    TRIG : BOOL;
    MSG : STRING;
    LEVEL : LOGLEVEL := INFO;
  END_VAR
  VAR
    TRIG0 : BOOL;
  END_VAR

  IF TRIG AND NOT TRIG0 THEN
  {{
   LogMessage(GetFbVar(LEVEL),(char*)GetFbVar(MSG, .body),GetFbVar(MSG, .len));
  }}
  END_IF;
  TRIG0:=TRIG;
END_FUNCTION_BLOCK


PROGRAM motor_ctrl
  VAR
    motor_error : BOOL;
    motor_error_true : BOOL;
    run_motor : BOOL;
    motor_running : BOOL;
    stop_motor : BOOL;
    run_motor_true : BOOL;
    motor_running_true : BOOL;
    stop_motor_true : BOOL;
    motor_rpm : INT;
    motor_rpm_true : INT;
    target_freq : INT;
    target_freq_true : INT := 120;
  END_VAR
  VAR
    R_TRIG1 : R_TRIG;
    R_TRIG2 : R_TRIG;
    R_TRIG3 : R_TRIG;
    _TMP_SEL17_OUT : INT;
  END_VAR

  R_TRIG1(CLK := run_motor);
  IF NOT(motor_error) AND R_TRIG1.Q THEN
    motor_running := TRUE; (*set*)
  END_IF;
  R_TRIG2(CLK := stop_motor);
  IF R_TRIG2.Q OR motor_error THEN
    motor_running := FALSE; (*reset*)
  END_IF;
  R_TRIG3(CLK := stop_motor);
  _TMP_SEL17_OUT := SEL(R_TRIG3.Q OR motor_error, target_freq, 0);
  target_freq := _TMP_SEL17_OUT;
END_PROGRAM


CONFIGURATION Config0

  RESOURCE Res0 ON PLC
    TASK task0(INTERVAL := T#20ms,PRIORITY := 0);
    PROGRAM instance0 WITH task0 : motor_ctrl;
  END_RESOURCE
END_CONFIGURATION
