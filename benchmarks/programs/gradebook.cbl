      *> Letter grade banding with fixed-width alphanumeric output.
      *> Gotcha 1: WS-NAME is PIC X(12); longer input is truncated on the
      *>           right and shorter input is space padded, and the DISPLAY
      *>           emits all twelve bytes.
      *> Gotcha 2: the boundary tests are >= on the lower edge, so 90
      *>           exactly is an A, not a B.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. GRADEBOOK.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-NAME             PIC X(12)   VALUE SPACES.
       01  WS-SCORE-1          PIC 9(3)     VALUE ZERO.
       01  WS-SCORE-2          PIC 9(3)     VALUE ZERO.
       01  WS-SCORE-3          PIC 9(3)     VALUE ZERO.
       01  WS-TOTAL            PIC 9(4)     VALUE ZERO.
       01  WS-AVG              PIC 9(3)V9  VALUE ZERO.
       01  WS-GRADE            PIC X        VALUE SPACE.
       01  WS-AVG-OUT          PIC ZZ9.9.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-NAME
           ACCEPT WS-SCORE-1
           ACCEPT WS-SCORE-2
           ACCEPT WS-SCORE-3
           COMPUTE WS-TOTAL = WS-SCORE-1 + WS-SCORE-2 + WS-SCORE-3
           DIVIDE WS-TOTAL BY 3 GIVING WS-AVG
           PERFORM BAND-GRADE
           MOVE WS-AVG TO WS-AVG-OUT
           DISPLAY "NAME  [" WS-NAME "]"
           DISPLAY "TOTAL " WS-TOTAL
           DISPLAY "AVG   " WS-AVG-OUT
           DISPLAY "GRADE " WS-GRADE
           STOP RUN.
       BAND-GRADE.
           IF WS-AVG >= 90
               MOVE "A" TO WS-GRADE
           ELSE
               IF WS-AVG >= 80
                   MOVE "B" TO WS-GRADE
               ELSE
                   IF WS-AVG >= 70
                       MOVE "C" TO WS-GRADE
                   ELSE
                       IF WS-AVG >= 60
                           MOVE "D" TO WS-GRADE
                       ELSE
                           MOVE "F" TO WS-GRADE
                       END-IF
                   END-IF
               END-IF
           END-IF.
