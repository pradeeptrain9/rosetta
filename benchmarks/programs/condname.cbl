      *> Condition names and boolean precedence.
      *> Gotcha 1: AND binds TIGHTER than OR, so
      *>           "A AND B OR C" is "(A AND B) OR C". A port that reads
      *>           left to right gets a different answer.
      *> Gotcha 2: an abbreviated combined relation - "IF X > 18 AND < 65" -
      *>           carries the subject and the operator forward.
      *> Gotcha 3: a level-88 with several values is an OR over all of them.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CONDNAME.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-STATUS           PIC X        VALUE SPACE.
           88  ST-ACTIVE                    VALUE "A".
           88  ST-CLOSED                    VALUE "C".
           88  ST-KNOWN                     VALUE "A" "C" "P".
       01  WS-AGE              PIC 9(3)     VALUE ZERO.
       01  WS-BAL              PIC 9(7)V99  VALUE ZERO.
       01  WS-TIER             PIC X(8)     VALUE SPACES.
       01  WS-BAND             PIC X(8)     VALUE SPACES.
       01  WS-KNOWN-FLAG       PIC X(3)     VALUE SPACES.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-STATUS
           ACCEPT WS-AGE
           ACCEPT WS-BAL
           IF ST-ACTIVE AND WS-AGE > 18 OR WS-BAL > 10000
               MOVE "PRIORITY" TO WS-TIER
           ELSE
               MOVE "STANDARD" TO WS-TIER
           END-IF
           IF WS-AGE > 18 AND < 65
               MOVE "WORKING" TO WS-BAND
           ELSE
               MOVE "OTHER" TO WS-BAND
           END-IF
           IF NOT ST-KNOWN
               MOVE "NO" TO WS-KNOWN-FLAG
           ELSE
               MOVE "YES" TO WS-KNOWN-FLAG
           END-IF
           DISPLAY "TIER   " WS-TIER
           DISPLAY "BAND   " WS-BAND
           DISPLAY "KNOWN  " WS-KNOWN-FLAG
           IF ST-CLOSED
               DISPLAY "CLOSED YES"
           ELSE
               DISPLAY "CLOSED NO"
           END-IF
           STOP RUN.
