      *> STRING and UNSTRING with an explicit POINTER.
      *> Gotcha 1: DELIMITED BY SPACE stops at the first space, so the
      *>           PIC X(10) padding is dropped - but DELIMITED BY SIZE
      *>           copies the whole field including padding.
      *> Gotcha 2: WITH POINTER is 1-based and is left pointing at the next
      *>           unused position AFTER the statement, not at the last
      *>           character written.
      *> Gotcha 3: UNSTRING TALLYING counts receiving fields FILLED, and
      *>           untouched receiving fields keep their previous contents
      *>           rather than being cleared.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. STRINGOPS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-FIRST            PIC X(10)    VALUE SPACES.
       01  WS-LAST             PIC X(10)    VALUE SPACES.
       01  WS-FULL             PIC X(25)    VALUE ALL "-".
       01  WS-PTR              PIC 9(3)     VALUE 1.
       01  WS-P1               PIC X(12)    VALUE "PREV1".
       01  WS-P2               PIC X(12)    VALUE "PREV2".
       01  WS-P3               PIC X(12)    VALUE "PREV3".
       01  WS-CNT              PIC 9(3)     VALUE ZERO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-FIRST
           ACCEPT WS-LAST
           MOVE 1 TO WS-PTR
           STRING WS-FIRST DELIMITED BY SPACE
                  "," DELIMITED BY SIZE
                  WS-LAST DELIMITED BY SPACE
               INTO WS-FULL
               WITH POINTER WS-PTR
           END-STRING
           DISPLAY "FULL  [" WS-FULL "]"
           DISPLAY "PTR    " WS-PTR
           UNSTRING WS-FULL
               DELIMITED BY ","
               INTO WS-P1 WS-P2 WS-P3
               TALLYING IN WS-CNT
           END-UNSTRING
           DISPLAY "P1    [" WS-P1 "]"
           DISPLAY "P2    [" WS-P2 "]"
           DISPLAY "P3    [" WS-P3 "]"
           DISPLAY "CNT    " WS-CNT
           STOP RUN.
