      *> Mod-10 (Luhn) check digit over a fixed 16 character field.
      *> Gotcha 1: PERFORM VARYING leaves WS-I at the first value that
      *>           failed the UNTIL test, and that value is DISPLAYed.
      *> Gotcha 2: non-digit characters are read through reference
      *>           modification and must behave exactly as GnuCOBOL does.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CHECKDIG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-CARD             PIC X(16)    VALUE SPACES.
       01  WS-I                PIC 9(2)     VALUE ZERO.
       01  WS-DIGIT            PIC 9        VALUE ZERO.
       01  WS-DOUBLED          PIC 9(2)     VALUE ZERO.
       01  WS-SUM              PIC 9(4)     VALUE ZERO.
       01  WS-CHECK            PIC 9        VALUE ZERO.
       01  WS-CHAR             PIC X        VALUE SPACE.
       01  WS-VALID-FLAG       PIC X        VALUE "N".
           88  CARD-VALID                   VALUE "Y".
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-CARD
           MOVE ZERO TO WS-SUM
           PERFORM VARYING WS-I FROM 16 BY -1 UNTIL WS-I < 1
               MOVE WS-CARD(WS-I:1) TO WS-CHAR
               IF WS-CHAR IS NUMERIC
                   MOVE WS-CHAR TO WS-DIGIT
               ELSE
                   MOVE ZERO TO WS-DIGIT
               END-IF
               COMPUTE WS-DOUBLED = FUNCTION MOD(WS-I, 2)
               IF WS-DOUBLED = 0
                   COMPUTE WS-DIGIT = WS-DIGIT * 2
                   IF WS-DIGIT > 9
                       SUBTRACT 9 FROM WS-DIGIT
                   END-IF
               END-IF
               ADD WS-DIGIT TO WS-SUM
           END-PERFORM
           COMPUTE WS-CHECK = FUNCTION MOD(WS-SUM, 10)
           IF WS-CHECK = 0
               MOVE "Y" TO WS-VALID-FLAG
           END-IF
           DISPLAY "SUM   " WS-SUM
           DISPLAY "CHECK " WS-CHECK
           IF CARD-VALID
               DISPLAY "STATUS VALID"
           ELSE
               DISPLAY "STATUS INVALID"
           END-IF
           DISPLAY "IDX   " WS-I
           STOP RUN.
