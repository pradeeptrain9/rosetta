      *> Character-driven state machine, no GO TO.
      *> Gotcha 1: PERFORM ... WITH TEST AFTER runs the body ONCE even when
      *>           the UNTIL condition is already true on entry. TEST BEFORE
      *>           (the default) does not.
      *> Gotcha 2: the VARYING loop exits on a compound OR, so the control
      *>           variable's final value depends on WHICH branch of the OR
      *>           ended it - and that value is displayed.
      *> Gotcha 3: a level-88 inside the UNTIL is re-evaluated every pass.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. STATEMACH.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-INPUT            PIC X(10)    VALUE SPACES.
       01  WS-CMD              PIC X        VALUE SPACE.
       01  WS-STATE            PIC X(8)     VALUE "IDLE".
       01  WS-STEPS            PIC 9(3)     VALUE ZERO.
       01  WS-REJECTS          PIC 9(3)     VALUE ZERO.
       01  WS-DONE             PIC X        VALUE "N".
           88  MACHINE-DONE                 VALUE "Y".
       01  WS-I                PIC 9(2)     VALUE ZERO.
       01  WS-K                PIC 9(2)     VALUE ZERO.
       01  WS-STEP-OUT         PIC Z9.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-INPUT
           PERFORM VARYING WS-I FROM 1 BY 1
                   UNTIL WS-I > 10 OR MACHINE-DONE
               MOVE WS-INPUT(WS-I:1) TO WS-CMD
               PERFORM STEP-MACHINE
               ADD 1 TO WS-STEPS
               MOVE WS-STEPS TO WS-STEP-OUT
               DISPLAY "STEP" WS-STEP-OUT " CMD [" WS-CMD "] -> "
                   WS-STATE
           END-PERFORM
           MOVE ZERO TO WS-K
           PERFORM WITH TEST AFTER UNTIL WS-K >= 0
               ADD 1 TO WS-K
           END-PERFORM
           DISPLAY "FINAL   " WS-STATE
           DISPLAY "STEPS   " WS-STEPS
           DISPLAY "REJECTS " WS-REJECTS
           DISPLAY "EXITIDX " WS-I
           DISPLAY "AFTERK  " WS-K
           STOP RUN.
       STEP-MACHINE.
           EVALUATE WS-STATE ALSO WS-CMD
               WHEN "IDLE"    ALSO "S"
                   MOVE "RUNNING" TO WS-STATE
               WHEN "RUNNING" ALSO "P"
                   MOVE "PAUSED" TO WS-STATE
               WHEN "PAUSED"  ALSO "S"
                   MOVE "RUNNING" TO WS-STATE
               WHEN ANY       ALSO "X"
                   MOVE "STOPPED" TO WS-STATE
                   MOVE "Y" TO WS-DONE
               WHEN ANY       ALSO SPACE
                   CONTINUE
               WHEN OTHER
                   ADD 1 TO WS-REJECTS
           END-EVALUATE.
