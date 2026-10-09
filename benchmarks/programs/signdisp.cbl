      *> How a signed value actually reaches stdout.
      *> Gotcha 1: a plain PIC S9(5) DISPLAY field carries its sign as an
      *>           OVERPUNCH on the last digit byte, so DISPLAY of -42 does
      *>           not print a minus sign at all.
      *> Gotcha 2: SIGN IS LEADING / TRAILING SEPARATE moves the sign into
      *>           its own byte and changes the field width.
      *> Gotcha 3: floating insertion -(5)9 right-justifies the sign next
      *>           to the first significant digit; +(5)9 always emits a sign.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SIGNDISP.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-VAL              PIC S9(5)    VALUE ZERO.
       01  WS-LEAD             PIC S9(5) SIGN IS LEADING SEPARATE
                                            VALUE ZERO.
       01  WS-TRAIL            PIC S9(5) SIGN IS TRAILING SEPARATE
                                            VALUE ZERO.
       01  WS-ED-MINUS         PIC -(5)9.
       01  WS-ED-PLUS          PIC +(5)9.
       01  WS-ABS              PIC 9(5)     VALUE ZERO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-VAL
           MOVE WS-VAL TO WS-LEAD
           MOVE WS-VAL TO WS-TRAIL
           MOVE WS-VAL TO WS-ED-MINUS
           MOVE WS-VAL TO WS-ED-PLUS
           COMPUTE WS-ABS = FUNCTION ABS(WS-VAL)
           DISPLAY "RAW   [" WS-VAL "]"
           DISPLAY "LEAD  [" WS-LEAD "]"
           DISPLAY "TRAIL [" WS-TRAIL "]"
           DISPLAY "EDM   [" WS-ED-MINUS "]"
           DISPLAY "EDP   [" WS-ED-PLUS "]"
           DISPLAY "ABS   [" WS-ABS "]"
           STOP RUN.
