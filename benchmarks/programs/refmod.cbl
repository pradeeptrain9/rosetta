      *> Reference modification with computed offsets.
      *> Gotcha 1: field(start:len) is 1-based and len is a LENGTH, not an
      *>           end position. Off-by-one here is silent.
      *> Gotcha 2: MOVE of a short substring into PIC X(16) pads the rest
      *>           with spaces; it does not leave the previous contents.
      *> Gotcha 3: writing single characters into a destination substring
      *>           leaves every position never written as its initial value.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. REFMOD.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-STR              PIC X(16)    VALUE SPACES.
       01  WS-START            PIC 9(2)     VALUE ZERO.
       01  WS-LEN              PIC 9(2)     VALUE ZERO.
       01  WS-PIECE            PIC X(16)    VALUE ALL "#".
       01  WS-REV              PIC X(16)    VALUE ALL ".".
       01  WS-I                PIC 9(2)     VALUE ZERO.
       01  WS-J                PIC 9(2)     VALUE ZERO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-STR
           ACCEPT WS-START
           ACCEPT WS-LEN
           PERFORM CLAMP-RANGE
           MOVE WS-STR(WS-START:WS-LEN) TO WS-PIECE
           MOVE 16 TO WS-J
           PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > 16
               MOVE WS-STR(WS-I:1) TO WS-REV(WS-J:1)
               SUBTRACT 1 FROM WS-J
           END-PERFORM
           DISPLAY "START  " WS-START
           DISPLAY "LEN    " WS-LEN
           DISPLAY "PIECE [" WS-PIECE "]"
           DISPLAY "REV   [" WS-REV "]"
           DISPLAY "TAIL  [" WS-STR(13:4) "]"
           STOP RUN.
       CLAMP-RANGE.
           IF WS-START < 1 OR WS-START > 16
               MOVE 1 TO WS-START
           END-IF
           IF WS-LEN < 1
               MOVE 1 TO WS-LEN
           END-IF
           IF WS-START + WS-LEN - 1 > 16
               COMPUTE WS-LEN = 17 - WS-START
           END-IF.
