      *> Truncation and rounding of the same value, side by side.
      *> Gotcha 1: MOVE from V999 to V99 TRUNCATES the third decimal.
      *>           COMPUTE ... ROUNDED on the same value rounds half away
      *>           from zero. Python's round() is half-to-even and gets
      *>           every exact .xx5 case wrong.
      *> Gotcha 2: DIVIDE ... REMAINDER stores the remainder with the sign
      *>           of the dividend and truncates the quotient.
      *> The value arrives as integer THOUSANDTHS: ACCEPT into a V-scaled
      *> field reads stdin as an integer, so the third decimal has to be
      *> produced by arithmetic or the rounding difference never appears.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ROUNDMODE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-MILLES           PIC 9(8)     VALUE ZERO.
       01  WS-AMT              PIC 9(5)V999 VALUE ZERO.
       01  WS-TRUNC            PIC 9(5)V99  VALUE ZERO.
       01  WS-ROUND            PIC 9(5)V99  VALUE ZERO.
       01  WS-WHOLE            PIC 9(5)     VALUE ZERO.
       01  WS-QUOT             PIC 9(5)     VALUE ZERO.
       01  WS-REM              PIC 9(2)     VALUE ZERO.
       01  WS-T-OUT            PIC Z(4)9.99.
       01  WS-R-OUT            PIC Z(4)9.99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-MILLES
           COMPUTE WS-AMT = WS-MILLES / 1000
           MOVE WS-AMT TO WS-TRUNC
           COMPUTE WS-ROUND ROUNDED = WS-AMT
           MOVE WS-AMT TO WS-WHOLE
           DIVIDE WS-WHOLE BY 7 GIVING WS-QUOT REMAINDER WS-REM
           MOVE WS-TRUNC TO WS-T-OUT
           MOVE WS-ROUND TO WS-R-OUT
           DISPLAY "TRUNC " WS-T-OUT
           DISPLAY "ROUND " WS-R-OUT
           DISPLAY "WHOLE " WS-WHOLE
           DISPLAY "QUOT  " WS-QUOT
           DISPLAY "REM   " WS-REM
           STOP RUN.
