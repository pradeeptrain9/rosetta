      *> Date arithmetic via the integer date intrinsics.
      *> Deterministic on purpose: both dates come from stdin, nothing reads
      *> the system clock, so the run is reproducible.
      *> Gotcha 1: INTEGER-OF-DATE counts days from 1601-01-01, so the raw
      *>           integers are large and the DIFFERENCE is the useful value.
      *> Gotcha 2: the input is normalised first, because an out-of-range
      *>           month or day makes the intrinsic undefined.
      *> Gotcha 3: DIVIDE ... REMAINDER on a signed dividend takes the sign
      *>           of the dividend, so a negative span yields a negative
      *>           remainder.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DATECALC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RAW-1            PIC 9(8)     VALUE ZERO.
       01  WS-RAW-2            PIC 9(8)     VALUE ZERO.
       01  WS-WORK-DATE        PIC 9(8)     VALUE ZERO.
       01  WS-YYYY             PIC 9(4)     VALUE ZERO.
       01  WS-MMDD             PIC 9(4)     VALUE ZERO.
       01  WS-MM               PIC 9(2)     VALUE ZERO.
       01  WS-DD               PIC 9(2)     VALUE ZERO.
       01  WS-INT-1            PIC 9(7)     VALUE ZERO.
       01  WS-INT-2            PIC 9(7)     VALUE ZERO.
       01  WS-SPAN             PIC S9(7)    VALUE ZERO.
       01  WS-WEEKS            PIC S9(5)    VALUE ZERO.
       01  WS-REM              PIC S9(2)    VALUE ZERO.
       01  WS-PLUS-100         PIC 9(8)     VALUE ZERO.
       01  WS-SPAN-OUT         PIC -(6)9.
       01  WS-WEEKS-OUT        PIC -(4)9.
       01  WS-REM-OUT          PIC -9.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-RAW-1
           ACCEPT WS-RAW-2
           MOVE WS-RAW-1 TO WS-WORK-DATE
           PERFORM NORMALIZE-DATE
           MOVE WS-WORK-DATE TO WS-RAW-1
           MOVE WS-RAW-2 TO WS-WORK-DATE
           PERFORM NORMALIZE-DATE
           MOVE WS-WORK-DATE TO WS-RAW-2
           COMPUTE WS-INT-1 = FUNCTION INTEGER-OF-DATE(WS-RAW-1)
           COMPUTE WS-INT-2 = FUNCTION INTEGER-OF-DATE(WS-RAW-2)
           COMPUTE WS-SPAN = WS-INT-2 - WS-INT-1
           DIVIDE WS-SPAN BY 7 GIVING WS-WEEKS REMAINDER WS-REM
           COMPUTE WS-PLUS-100 =
               FUNCTION DATE-OF-INTEGER(WS-INT-1 + 100)
           MOVE WS-SPAN  TO WS-SPAN-OUT
           MOVE WS-WEEKS TO WS-WEEKS-OUT
           MOVE WS-REM   TO WS-REM-OUT
           DISPLAY "DATE1 " WS-RAW-1
           DISPLAY "DATE2 " WS-RAW-2
           DISPLAY "SPAN  " WS-SPAN-OUT
           DISPLAY "WEEKS " WS-WEEKS-OUT
           DISPLAY "REM   " WS-REM-OUT
           DISPLAY "PLUS  " WS-PLUS-100
           STOP RUN.
       NORMALIZE-DATE.
           DIVIDE WS-WORK-DATE BY 10000 GIVING WS-YYYY
               REMAINDER WS-MMDD
           DIVIDE WS-MMDD BY 100 GIVING WS-MM REMAINDER WS-DD
           IF WS-YYYY < 1700 OR WS-YYYY > 9000
               MOVE 2000 TO WS-YYYY
           END-IF
           IF WS-MM < 1 OR WS-MM > 12
               MOVE 1 TO WS-MM
           END-IF
           IF WS-DD < 1 OR WS-DD > 28
               MOVE 1 TO WS-DD
           END-IF
           COMPUTE WS-WORK-DATE =
               WS-YYYY * 10000 + WS-MM * 100 + WS-DD.
