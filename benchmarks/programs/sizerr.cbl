      *> The same overflow, with and without ON SIZE ERROR.
      *> Gotcha: when ON SIZE ERROR is present and fires, the receiving
      *>         field is left COMPLETELY UNCHANGED - it keeps whatever it
      *>         held before. Without the clause the high-order digits are
      *>         silently discarded and the field holds the low-order
      *>         remainder. Two different wrong answers from one overflow.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SIZERR.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-A                PIC 9(3)     VALUE ZERO.
       01  WS-B                PIC 9(3)     VALUE ZERO.
       01  WS-GUARDED          PIC 9(3)     VALUE 777.
       01  WS-UNGUARDED        PIC 9(3)     VALUE 777.
       01  WS-WIDE             PIC 9(7)     VALUE ZERO.
       01  WS-FLAG             PIC X(8)     VALUE "OK".
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-A
           ACCEPT WS-B
           COMPUTE WS-GUARDED = WS-A * WS-B
               ON SIZE ERROR
                   MOVE "OVERFLOW" TO WS-FLAG
           END-COMPUTE
           MULTIPLY WS-A BY WS-B GIVING WS-UNGUARDED
           MULTIPLY WS-A BY WS-B GIVING WS-WIDE
           DISPLAY "GUARDED   " WS-GUARDED
           DISPLAY "UNGUARDED " WS-UNGUARDED
           DISPLAY "WIDE      " WS-WIDE
           DISPLAY "FLAG      " WS-FLAG
           STOP RUN.
