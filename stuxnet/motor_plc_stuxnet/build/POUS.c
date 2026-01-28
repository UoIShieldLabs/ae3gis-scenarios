void LOGGER_init__(LOGGER *data__, BOOL retain) {
  __INIT_VAR(data__->EN,__BOOL_LITERAL(TRUE),retain)
  __INIT_VAR(data__->ENO,__BOOL_LITERAL(TRUE),retain)
  __INIT_VAR(data__->TRIG,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->MSG,__STRING_LITERAL(0,""),retain)
  __INIT_VAR(data__->LEVEL,LOGLEVEL__INFO,retain)
  __INIT_VAR(data__->TRIG0,__BOOL_LITERAL(FALSE),retain)
}

// Code part
void LOGGER_body__(LOGGER *data__) {
  // Control execution
  if (!__GET_VAR(data__->EN)) {
    __SET_VAR(data__->,ENO,,__BOOL_LITERAL(FALSE));
    return;
  }
  else {
    __SET_VAR(data__->,ENO,,__BOOL_LITERAL(TRUE));
  }
  // Initialise TEMP variables

  if ((__GET_VAR(data__->TRIG,) && !(__GET_VAR(data__->TRIG0,)))) {
    #define GetFbVar(var,...) __GET_VAR(data__->var,__VA_ARGS__)
    #define SetFbVar(var,val,...) __SET_VAR(data__->,var,__VA_ARGS__,val)

   LogMessage(GetFbVar(LEVEL),(char*)GetFbVar(MSG, .body),GetFbVar(MSG, .len));
  
    #undef GetFbVar
    #undef SetFbVar
;
  };
  __SET_VAR(data__->,TRIG0,,__GET_VAR(data__->TRIG,));

  goto __end;

__end:
  return;
} // LOGGER_body__() 





void MOTOR_CTRL_init__(MOTOR_CTRL *data__, BOOL retain) {
  __INIT_VAR(data__->MOTOR_ERROR,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->MOTOR_ERROR_TRUE,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->RUN_MOTOR,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->MOTOR_RUNNING,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->STOP_MOTOR,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->RUN_MOTOR_TRUE,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->MOTOR_RUNNING_TRUE,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->STOP_MOTOR_TRUE,__BOOL_LITERAL(FALSE),retain)
  __INIT_VAR(data__->MOTOR_RPM,0,retain)
  __INIT_VAR(data__->MOTOR_RPM_TRUE,0,retain)
  __INIT_VAR(data__->TARGET_FREQ,0,retain)
  __INIT_VAR(data__->TARGET_FREQ_TRUE,120,retain)
  R_TRIG_init__(&data__->R_TRIG1,retain);
  R_TRIG_init__(&data__->R_TRIG2,retain);
  R_TRIG_init__(&data__->R_TRIG3,retain);
  __INIT_VAR(data__->_TMP_SEL17_OUT,0,retain)
}

// Code part
void MOTOR_CTRL_body__(MOTOR_CTRL *data__) {
  // Initialise TEMP variables

  __SET_VAR(data__->R_TRIG1.,CLK,,__GET_VAR(data__->RUN_MOTOR,));
  R_TRIG_body__(&data__->R_TRIG1);
  if ((!(__GET_VAR(data__->MOTOR_ERROR,)) && __GET_VAR(data__->R_TRIG1.Q,))) {
    __SET_VAR(data__->,MOTOR_RUNNING,,__BOOL_LITERAL(TRUE));
  };
  __SET_VAR(data__->R_TRIG2.,CLK,,__GET_VAR(data__->STOP_MOTOR,));
  R_TRIG_body__(&data__->R_TRIG2);
  if ((__GET_VAR(data__->R_TRIG2.Q,) || __GET_VAR(data__->MOTOR_ERROR,))) {
    __SET_VAR(data__->,MOTOR_RUNNING,,__BOOL_LITERAL(FALSE));
  };
  __SET_VAR(data__->R_TRIG3.,CLK,,__GET_VAR(data__->STOP_MOTOR,));
  R_TRIG_body__(&data__->R_TRIG3);
  __SET_VAR(data__->,_TMP_SEL17_OUT,,SEL__INT__BOOL__INT__INT(
    (BOOL)__BOOL_LITERAL(TRUE),
    NULL,
    (BOOL)(__GET_VAR(data__->R_TRIG3.Q,) || __GET_VAR(data__->MOTOR_ERROR,)),
    (INT)__GET_VAR(data__->TARGET_FREQ,),
    (INT)0));
  __SET_VAR(data__->,TARGET_FREQ,,__GET_VAR(data__->_TMP_SEL17_OUT,));

  goto __end;

__end:
  return;
} // MOTOR_CTRL_body__() 





