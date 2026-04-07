FUNCTION_BLOCK Reg1_IdleCtrl
  VAR_OUTPUT
    engage_gen : BOOL;
    pitch_setpoint : REAL;
    tq_setpoint : REAL;
  END_VAR

  engage_gen := 0;
  pitch_setpoint := 0.0;
  tq_setpoint := 0.0;
END_FUNCTION_BLOCK

FUNCTION_BLOCK Reg1_5_GenTorqueCtrl
  VAR_INPUT
    gen_speed : REAL;
    r1_5_speed : REAL;
    r2_speed : REAL;
    k : REAL;
  END_VAR
  VAR_OUTPUT
    engage_gen : BOOL;
    pitch_setpoint : REAL;
    tq_setpoint : REAL;
  END_VAR
  VAR
    _TMP_MUL8_OUT : REAL;
    _TMP_MUL9_OUT : REAL;
    _TMP_SUB10_OUT : REAL;
    _TMP_DIV11_OUT : REAL;
    _TMP_SUB13_OUT : REAL;
    _TMP_MUL14_OUT : REAL;
  END_VAR

  engage_gen := 1;
  pitch_setpoint := 0.0;
  _TMP_MUL8_OUT := MUL(r2_speed, r2_speed);
  _TMP_MUL9_OUT := MUL(k, _TMP_MUL8_OUT);
  _TMP_SUB10_OUT := SUB(r2_speed, r1_5_speed);
  _TMP_DIV11_OUT := DIV(_TMP_MUL9_OUT, _TMP_SUB10_OUT);
  _TMP_SUB13_OUT := SUB(gen_speed, r1_5_speed);
  _TMP_MUL14_OUT := MUL(_TMP_DIV11_OUT, _TMP_SUB13_OUT);
  tq_setpoint := _TMP_MUL14_OUT;
END_FUNCTION_BLOCK

FUNCTION_BLOCK Reg2_GenTorqueCtrl
  VAR_INPUT
    gen_speed : REAL;
    rated_tq : REAL;
    k : REAL;
  END_VAR
  VAR_OUTPUT
    engage_gen : BOOL;
    pitch_setpoint : REAL;
    tq_setpoint : REAL;
  END_VAR
  VAR
    _TMP_MUL9_OUT : REAL;
    _TMP_MUL6_OUT : REAL;
    _TMP_LIMIT12_OUT : REAL;
  END_VAR

  engage_gen := 1;
  pitch_setpoint := 0.0;
  _TMP_MUL9_OUT := MUL(gen_speed, gen_speed);
  _TMP_MUL6_OUT := MUL(k, _TMP_MUL9_OUT);
  _TMP_LIMIT12_OUT := LIMIT(0.0, _TMP_MUL6_OUT, rated_tq);
  tq_setpoint := _TMP_LIMIT12_OUT;
END_FUNCTION_BLOCK

FUNCTION_BLOCK Reg2_5_GenTorqueCtrl
  VAR_INPUT
    gen_speed : REAL;
    rated_gen_speed : REAL;
    rated_gen_tq : REAL;
    rated_gen_elec_power : REAL;
    gen_efficiency : REAL;
    slip_perc : REAL;
  END_VAR
  VAR_OUTPUT
    engage_gen : BOOL;
    pitch_setpoint : REAL;
    tq_setpoint : REAL;
  END_VAR
  VAR
    _TMP_DIV12_OUT : REAL;
    _TMP_DIV20_OUT : REAL;
    _TMP_MUL7_OUT : REAL;
    _TMP_ADD8_OUT : REAL;
    _TMP_DIV15_OUT : REAL;
    _TMP_SUB21_OUT : REAL;
    _TMP_DIV22_OUT : REAL;
    _TMP_SUB27_OUT : REAL;
    _TMP_MUL28_OUT : REAL;
    _TMP_LIMIT30_OUT : REAL;
  END_VAR

  engage_gen := 1;
  pitch_setpoint := 0.0;
  _TMP_DIV12_OUT := DIV(rated_gen_elec_power, gen_efficiency);
  _TMP_DIV20_OUT := DIV(_TMP_DIV12_OUT, rated_gen_speed);
  _TMP_MUL7_OUT := MUL(slip_perc, 0.01);
  _TMP_ADD8_OUT := ADD(_TMP_MUL7_OUT, 1.0);
  _TMP_DIV15_OUT := DIV(rated_gen_speed, _TMP_ADD8_OUT);
  _TMP_SUB21_OUT := SUB(rated_gen_speed, _TMP_DIV15_OUT);
  _TMP_DIV22_OUT := DIV(_TMP_DIV20_OUT, _TMP_SUB21_OUT);
  _TMP_SUB27_OUT := SUB(gen_speed, _TMP_DIV15_OUT);
  _TMP_MUL28_OUT := MUL(_TMP_DIV22_OUT, _TMP_SUB27_OUT);
  _TMP_LIMIT30_OUT := LIMIT(0.0, _TMP_MUL28_OUT, rated_gen_tq);
  tq_setpoint := _TMP_LIMIT30_OUT;
END_FUNCTION_BLOCK

FUNCTION_BLOCK Reg3_PitchCtrl
  VAR_INPUT
    PI_setpoint : REAL;
    PI_measurement : REAL;
    Kp : REAL;
    Ki : REAL;
    lambda : REAL;
    cycle_time : REAL;
  END_VAR
  VAR_OUTPUT
    engage_gen : BOOL;
    pitch_setpoint : REAL;
  END_VAR
  VAR
    integrated_error : REAL := 0.0;
    _TMP_SUB16_OUT : REAL;
    _TMP_MUL17_OUT : REAL;
    _TMP_SUB3_OUT : REAL;
    _TMP_MUL19_OUT : REAL;
    _TMP_ADD20_OUT : REAL;
    _TMP_MUL8_OUT : REAL;
    _TMP_MUL22_OUT : REAL;
    _TMP_ADD27_OUT : REAL;
    _TMP_LIMIT28_OUT : REAL;
  END_VAR

  _TMP_SUB16_OUT := SUB(1.0, lambda);
  _TMP_MUL17_OUT := MUL(_TMP_SUB16_OUT, integrated_error);
  _TMP_SUB3_OUT := SUB(PI_measurement, PI_setpoint);
  _TMP_MUL19_OUT := MUL(_TMP_SUB3_OUT, cycle_time);
  _TMP_ADD20_OUT := ADD(_TMP_MUL17_OUT, _TMP_MUL19_OUT);
  integrated_error := _TMP_ADD20_OUT;
  _TMP_MUL8_OUT := MUL(_TMP_SUB3_OUT, Kp);
  _TMP_MUL22_OUT := MUL(_TMP_ADD20_OUT, Ki);
  _TMP_ADD27_OUT := ADD(_TMP_MUL8_OUT, _TMP_MUL22_OUT);
  _TMP_LIMIT28_OUT := LIMIT(0.0, _TMP_ADD27_OUT, 90.0);
  pitch_setpoint := _TMP_LIMIT28_OUT;
  engage_gen := 1;
END_FUNCTION_BLOCK

FUNCTION_BLOCK OverspeedCtrl
  VAR_OUTPUT
    engage_gen : BOOL;
    pitch_setpoint : REAL;
    tq_setpoint : REAL;
  END_VAR

  engage_gen := 0;
  pitch_setpoint := 90.0;
  tq_setpoint := 0.0;
END_FUNCTION_BLOCK

FUNCTION Find_Ctrl_Region : REAL
  VAR_INPUT
    gen_speed : REAL;
    wind_speed : REAL;
    r1_5_speed : REAL;
    r2_speed : REAL;
    r2_5_speed : REAL;
    r3_speed : REAL;
    wind_cut_out : REAL;
  END_VAR
  VAR_OUTPUT
    region_1 : BOOL;
    region_1_5 : BOOL;
    region_2 : BOOL;
    region_2_5 : BOOL;
    region_3 : BOOL;
    overspeed : BOOL;
  END_VAR

  IF wind_speed < wind_cut_out THEN
    IF gen_speed < r1_5_speed THEN
      region_1 := true;
      region_1_5 := false;
      region_2 := false;
      region_2_5 := false;
      region_3 := false;
      overspeed := false;
      Find_Ctrl_Region := 1.0;
    ELSIF gen_speed >= r1_5_speed AND gen_speed < r2_speed THEN
      region_1 := false;
      region_1_5 := true;
      region_2 := false;
      region_2_5 := false;
      region_3 := false;
      overspeed := false;
      Find_Ctrl_Region := 1.5;
    ELSIF gen_speed >= r2_speed AND gen_speed < r2_5_speed THEN
      region_1 := false;
      region_1_5 := false;
      region_2 := true;
      region_2_5 := false;
      region_3 := false;
      overspeed := false;
      Find_Ctrl_Region := 2.0;
    ELSIF gen_speed >= r2_5_speed AND gen_speed < r3_speed THEN
      region_1 := false;
      region_1_5 := false;
      region_2 := false;
      region_2_5 := true;
      region_3 := false;
      overspeed := false;
      Find_Ctrl_Region := 2.5;
    ELSE
      region_1 := false;
      region_1_5 := false;
      region_2 := false;
      region_2_5 := false;
      region_3 := true;
      overspeed := false;
      Find_Ctrl_Region := 3.0;
    END_IF;
  ELSE
    region_1 := false;
    region_1_5 := false;
    region_2 := false;
    region_2_5 := false;
    region_3 := false;
    overspeed := true;
    Find_Ctrl_Region := 0.0;
  END_IF;
END_FUNCTION

FUNCTION Two_WORDS_TO_REAL : REAL
  VAR_INPUT
    h_word : WORD;
    l_word : WORD;
    scaling : REAL;
  END_VAR
  VAR
    _TMP_WORD_TO_DWORD3_OUT : DWORD;
    _TMP_SHL5_OUT : DWORD;
    _TMP_WORD_TO_DWORD4_OUT : DWORD;
    _TMP_OR7_OUT : DWORD;
    _TMP_DWORD_TO_DINT8_OUT : DINT;
    _TMP_DINT_TO_REAL9_OUT : REAL;
    _TMP_DIV10_OUT : REAL;
  END_VAR

  _TMP_WORD_TO_DWORD3_OUT := WORD_TO_DWORD(h_word);
  _TMP_SHL5_OUT := SHL(_TMP_WORD_TO_DWORD3_OUT, 16);
  _TMP_WORD_TO_DWORD4_OUT := WORD_TO_DWORD(l_word);
  _TMP_OR7_OUT := OR(_TMP_SHL5_OUT, _TMP_WORD_TO_DWORD4_OUT);
  _TMP_DWORD_TO_DINT8_OUT := DWORD_TO_DINT(_TMP_OR7_OUT);
  _TMP_DINT_TO_REAL9_OUT := DINT_TO_REAL(_TMP_DWORD_TO_DINT8_OUT);
  _TMP_DIV10_OUT := DIV(_TMP_DINT_TO_REAL9_OUT, scaling);
  Two_WORDS_TO_REAL := _TMP_DIV10_OUT;
END_FUNCTION

FUNCTION REAL_TO_Two_WORDS : WORD
  VAR_INPUT
    in : REAL;
    scaling : REAL;
  END_VAR
  VAR_OUTPUT
    h_word : WORD;
    l_word : WORD;
  END_VAR
  VAR
    _TMP_MUL3_OUT : REAL;
    _TMP_REAL_TO_DINT4_OUT : DINT;
    _TMP_DINT_TO_DWORD5_OUT : DWORD;
    _TMP_SHR8_OUT : DWORD;
    _TMP_DWORD_TO_WORD6_OUT : WORD;
    _TMP_AND11_OUT : DWORD;
    _TMP_DWORD_TO_WORD7_OUT : WORD;
  END_VAR

  _TMP_MUL3_OUT := MUL(in, scaling);
  _TMP_REAL_TO_DINT4_OUT := REAL_TO_DINT(_TMP_MUL3_OUT);
  _TMP_DINT_TO_DWORD5_OUT := DINT_TO_DWORD(_TMP_REAL_TO_DINT4_OUT);
  _TMP_SHR8_OUT := SHR(_TMP_DINT_TO_DWORD5_OUT, 16);
  _TMP_DWORD_TO_WORD6_OUT := DWORD_TO_WORD(_TMP_SHR8_OUT);
  h_word := _TMP_DWORD_TO_WORD6_OUT;
  _TMP_AND11_OUT := AND(_TMP_DINT_TO_DWORD5_OUT, 16#FFFF);
  _TMP_DWORD_TO_WORD7_OUT := DWORD_TO_WORD(_TMP_AND11_OUT);
  l_word := _TMP_DWORD_TO_WORD7_OUT;
END_FUNCTION

PROGRAM program0
  VAR
    engage_gen AT %QX0.0 : BOOL;
    wind_speed_H AT %IW0 : WORD;
    wind_speed_L AT %IW1 : WORD;
    pitch_real_H AT %IW2 : WORD;
    pitch_real_L AT %IW3 : WORD;
    gen_power_H AT %IW4 : WORD;
    gen_power_L AT %IW5 : WORD;
    rot_speed_H AT %IW6 : WORD;
    rot_speed_L AT %IW7 : WORD;
    tsr_H AT %IW8 : WORD;
    tsr_L AT %IW9 : WORD;
    gen_tq_real_H AT %IW10 : WORD;
    gen_tq_real_L AT %IW11 : WORD;
    gen_speed_H AT %IW12 : WORD;
    gen_speed_L AT %IW13 : WORD;
    pitch_setpoint_H AT %QW0 : WORD;
    pitch_setpoint_L AT %QW1 : WORD;
    gen_tq_H AT %QW2 : WORD;
    gen_tq_L AT %QW3 : WORD;
    Ctrl_Reg_H AT %QW4 : WORD;
    Ctrl_Reg_L AT %QW5 : WORD;
  END_VAR
  VAR
    gen_speed_r1_5 : REAL := 70.16224;
    gen_speed_r2 : REAL := 91.21091;
    gen_speed_r2_5 : REAL := 121.68057;
    gen_speed_r3 : REAL := 122.90967;
    rated_gen_speed : REAL := 122.90967;
    wind_cut_out_speed : REAL := 25.0;
    SCALING : REAL := 1000.0;
    Tq_Ctrl_Gain : REAL := 2.309;
    r2_5_slip_perc : REAL := 10.0;
    gen_eff : REAL := 0.944;
    rated_gen_tq : REAL := 40680.0;
    rated_gen_power : REAL := 5000000.0;
    rotor_idle_speed : REAL := 0.5;
    pitch_sp_REAL : REAL;
    tq_sp_REAL : REAL;
    Reg1_IdleCtrl0 : Reg1_IdleCtrl;
    Reg1_5_GenTorqueCtrl0 : Reg1_5_GenTorqueCtrl;
    Reg2_GenTorqueCtrl0 : Reg2_GenTorqueCtrl;
    Reg2_5_GenTorqueCtrl0 : Reg2_5_GenTorqueCtrl;
    Reg3_PitchCtrl0 : Reg3_PitchCtrl;
    OverspeedCtrl0 : OverspeedCtrl;
    _TMP_Two_WORDS_TO_REAL4_OUT : REAL;
    _TMP_Two_WORDS_TO_REAL26_OUT : REAL;
    _TMP_Find_Ctrl_Region29_OUT : REAL;
    _TMP_Find_Ctrl_Region29_region_1 : BOOL;
    _TMP_Find_Ctrl_Region29_region_1_5 : BOOL;
    _TMP_Find_Ctrl_Region29_region_2 : BOOL;
    _TMP_Find_Ctrl_Region29_region_2_5 : BOOL;
    _TMP_Find_Ctrl_Region29_region_3 : BOOL;
    _TMP_Find_Ctrl_Region29_overspeed : BOOL;
    _TMP_REAL_TO_Two_WORDS62_OUT : WORD;
    _TMP_REAL_TO_Two_WORDS62_h_word : WORD;
    _TMP_REAL_TO_Two_WORDS62_l_word : WORD;
    _TMP_REAL_TO_Two_WORDS67_OUT : WORD;
    _TMP_REAL_TO_Two_WORDS67_h_word : WORD;
    _TMP_REAL_TO_Two_WORDS67_l_word : WORD;
    _TMP_REAL_TO_Two_WORDS74_OUT : WORD;
    _TMP_REAL_TO_Two_WORDS74_h_word : WORD;
    _TMP_REAL_TO_Two_WORDS74_l_word : WORD;
  END_VAR

  _TMP_Two_WORDS_TO_REAL4_OUT := Two_WORDS_TO_REAL(gen_speed_H, gen_speed_L, SCALING);
  _TMP_Two_WORDS_TO_REAL26_OUT := Two_WORDS_TO_REAL(wind_speed_H, wind_speed_L, SCALING);
  _TMP_Find_Ctrl_Region29_OUT := Find_Ctrl_Region(gen_speed := _TMP_Two_WORDS_TO_REAL4_OUT, wind_speed := _TMP_Two_WORDS_TO_REAL26_OUT, r1_5_speed := gen_speed_r1_5, r2_speed := gen_speed_r2, r2_5_speed := gen_speed_r2_5, r3_speed := gen_speed_r3, wind_cut_out := wind_cut_out_speed, region_1 => _TMP_Find_Ctrl_Region29_region_1, region_1_5 => _TMP_Find_Ctrl_Region29_region_1_5, region_2 => _TMP_Find_Ctrl_Region29_region_2, region_2_5 => _TMP_Find_Ctrl_Region29_region_2_5, region_3 => _TMP_Find_Ctrl_Region29_region_3, overspeed => _TMP_Find_Ctrl_Region29_overspeed);
  Reg1_IdleCtrl0(EN := _TMP_Find_Ctrl_Region29_region_1);
  IF Reg1_IdleCtrl0.ENO THEN
      engage_gen := Reg1_IdleCtrl0.engage_gen;
  END_IF;
  Reg1_5_GenTorqueCtrl0(EN := _TMP_Find_Ctrl_Region29_region_1_5, gen_speed := _TMP_Two_WORDS_TO_REAL4_OUT, r1_5_speed := gen_speed_r1_5, r2_speed := gen_speed_r2, k := Tq_Ctrl_Gain);
  IF Reg1_5_GenTorqueCtrl0.ENO THEN
      engage_gen := Reg1_5_GenTorqueCtrl0.engage_gen;
  END_IF;
  Reg2_GenTorqueCtrl0(EN := _TMP_Find_Ctrl_Region29_region_2, gen_speed := _TMP_Two_WORDS_TO_REAL4_OUT, rated_tq := rated_gen_tq, k := Tq_Ctrl_Gain);
  IF Reg2_GenTorqueCtrl0.ENO THEN
      engage_gen := Reg2_GenTorqueCtrl0.engage_gen;
  END_IF;
  Reg2_5_GenTorqueCtrl0(EN := _TMP_Find_Ctrl_Region29_region_2_5, gen_speed := _TMP_Two_WORDS_TO_REAL4_OUT, rated_gen_speed := rated_gen_speed, rated_gen_tq := rated_gen_tq, rated_gen_elec_power := rated_gen_power, gen_efficiency := gen_eff, slip_perc := r2_5_slip_perc);
  IF Reg2_5_GenTorqueCtrl0.ENO THEN
      engage_gen := Reg2_5_GenTorqueCtrl0.engage_gen;
  END_IF;
  Reg3_PitchCtrl0(EN := _TMP_Find_Ctrl_Region29_region_3, PI_setpoint := rated_gen_speed, PI_measurement := _TMP_Two_WORDS_TO_REAL4_OUT, Kp := 1.5, Ki := 3.0, lambda := 0.02, cycle_time := 0.02);
  IF Reg3_PitchCtrl0.ENO THEN
      engage_gen := Reg3_PitchCtrl0.engage_gen;
  END_IF;
  OverspeedCtrl0(EN := _TMP_Find_Ctrl_Region29_overspeed);
  IF OverspeedCtrl0.ENO THEN
      engage_gen := OverspeedCtrl0.engage_gen;
  END_IF;
  _TMP_REAL_TO_Two_WORDS62_OUT := REAL_TO_Two_WORDS(in := _TMP_Find_Ctrl_Region29_OUT, scaling := SCALING, h_word => _TMP_REAL_TO_Two_WORDS62_h_word, l_word => _TMP_REAL_TO_Two_WORDS62_l_word);
  Ctrl_Reg_H := _TMP_REAL_TO_Two_WORDS62_h_word;
  Ctrl_Reg_L := _TMP_REAL_TO_Two_WORDS62_l_word;
  _TMP_REAL_TO_Two_WORDS67_OUT := REAL_TO_Two_WORDS(in := pitch_sp_REAL, scaling := SCALING, h_word => _TMP_REAL_TO_Two_WORDS67_h_word, l_word => _TMP_REAL_TO_Two_WORDS67_l_word);
  pitch_setpoint_H := _TMP_REAL_TO_Two_WORDS67_h_word;
  pitch_setpoint_L := _TMP_REAL_TO_Two_WORDS67_l_word;
  _TMP_REAL_TO_Two_WORDS74_OUT := REAL_TO_Two_WORDS(in := tq_sp_REAL, scaling := SCALING, h_word => _TMP_REAL_TO_Two_WORDS74_h_word, l_word => _TMP_REAL_TO_Two_WORDS74_l_word);
  gen_tq_H := _TMP_REAL_TO_Two_WORDS74_h_word;
  gen_tq_L := _TMP_REAL_TO_Two_WORDS74_l_word;
  IF Reg1_IdleCtrl0.ENO THEN
      pitch_sp_REAL := Reg1_IdleCtrl0.pitch_setpoint;
  END_IF;
  IF Reg1_IdleCtrl0.ENO THEN
      tq_sp_REAL := Reg1_IdleCtrl0.tq_setpoint;
  END_IF;
  IF Reg1_5_GenTorqueCtrl0.ENO THEN
      pitch_sp_REAL := Reg1_5_GenTorqueCtrl0.pitch_setpoint;
  END_IF;
  IF Reg1_5_GenTorqueCtrl0.ENO THEN
      tq_sp_REAL := Reg1_5_GenTorqueCtrl0.tq_setpoint;
  END_IF;
  IF Reg2_GenTorqueCtrl0.ENO THEN
      pitch_sp_REAL := Reg2_GenTorqueCtrl0.pitch_setpoint;
  END_IF;
  IF Reg2_GenTorqueCtrl0.ENO THEN
      tq_sp_REAL := Reg2_GenTorqueCtrl0.tq_setpoint;
  END_IF;
  IF Reg2_5_GenTorqueCtrl0.ENO THEN
      pitch_sp_REAL := Reg2_5_GenTorqueCtrl0.pitch_setpoint;
  END_IF;
  IF Reg2_5_GenTorqueCtrl0.ENO THEN
      tq_sp_REAL := Reg2_5_GenTorqueCtrl0.tq_setpoint;
  END_IF;
  IF Reg3_PitchCtrl0.ENO THEN
      pitch_sp_REAL := Reg3_PitchCtrl0.pitch_setpoint;
  END_IF;
  IF OverspeedCtrl0.ENO THEN
      pitch_sp_REAL := OverspeedCtrl0.pitch_setpoint;
  END_IF;
  IF OverspeedCtrl0.ENO THEN
      tq_sp_REAL := OverspeedCtrl0.tq_setpoint;
  END_IF;
END_PROGRAM


CONFIGURATION Config0

  RESOURCE Res0 ON PLC
    TASK task0(INTERVAL := T#100ms,PRIORITY := 0);
    PROGRAM instance0 WITH task0 : program0;
  END_RESOURCE
END_CONFIGURATION