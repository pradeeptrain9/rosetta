      *> EVALUATE with THRU ranges and two subjects.
      *> Gotcha 1: the FIRST matching WHEN wins and the rest are skipped,
      *>           so overlapping branches are order dependent.
      *> Gotcha 2: ANY matches anything, including values a later, more
      *>           specific WHEN was written to catch - that later branch
      *>           is then dead code.
      *> Gotcha 3: THRU bounds are INCLUSIVE at both ends.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EVALRANGE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-CODE             PIC 9(2)     VALUE ZERO.
       01  WS-REGION           PIC X        VALUE SPACE.
       01  WS-FEE              PIC 9(4)V99  VALUE ZERO.
       01  WS-LABEL            PIC X(10)    VALUE SPACES.
       01  WS-FEE-OUT          PIC Z(3)9.99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-CODE
           ACCEPT WS-REGION
           EVALUATE WS-CODE ALSO WS-REGION
               WHEN 1 THRU 9   ALSO "N"
                   MOVE 10.50 TO WS-FEE
                   MOVE "NORTH-LOW" TO WS-LABEL
               WHEN 1 THRU 9   ALSO ANY
                   MOVE 12.75 TO WS-FEE
                   MOVE "ANY-LOW" TO WS-LABEL
               WHEN 10 THRU 49 ALSO "N"
                   MOVE 22.00 TO WS-FEE
                   MOVE "NORTH-MID" TO WS-LABEL
               WHEN ANY        ALSO "S"
                   MOVE 31.25 TO WS-FEE
                   MOVE "SOUTH-ALL" TO WS-LABEL
               WHEN 10 THRU 49 ALSO "S"
                   MOVE 99.99 TO WS-FEE
                   MOVE "DEAD-CODE" TO WS-LABEL
               WHEN OTHER
                   MOVE 45.00 TO WS-FEE
                   MOVE "FALLBACK" TO WS-LABEL
           END-EVALUATE
           MOVE WS-FEE TO WS-FEE-OUT
           DISPLAY "LABEL " WS-LABEL
           DISPLAY "FEE   " WS-FEE-OUT
           STOP RUN.
