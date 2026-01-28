PROGRAM motor_ctrl
  VAR
    motor_error AT %IX0.0 : BOOL;
    motor_error_true AT %IX0.1 : BOOL;
    run_motor AT %QX0.0 : BOOL;
    motor_running AT %QX0.1 : BOOL;
    stop_motor AT %QX0.2 : BOOL;
    run_motor_true AT %QX0.3 : BOOL;
    motor_running_true AT %QX0.4 : BOOL;
    stop_motor_true AT %QX0.5 : BOOL;
    motor_rpm AT %IW0 : INT;
    motor_rpm_true AT %IW1 : INT;
    target_freq AT %QW0 : INT;
    target_freq_true AT %QW1 : INT := 120;
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
