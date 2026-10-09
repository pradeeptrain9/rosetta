      *> OCCURS table with SEARCH, plus a subscripted accumulation loop.
      *> Gotcha 1: when SEARCH hits AT END the index is left ONE PAST the
      *>           table, so a program that reports the index afterwards
      *>           reports 6 for a five-entry table.
      *> Gotcha 2: SET moves an index to a numeric item by occurrence
      *>           number, not by byte offset.
      *> Gotcha 3: subscripts are 1-based and unchecked by default.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TABLESUM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TABLE.
           05  WS-ENTRY OCCURS 5 TIMES INDEXED BY WS-IDX.
               10  WS-CODE     PIC X(3).
               10  WS-QTY      PIC 9(4).
       01  WS-TARGET           PIC X(3)     VALUE SPACES.
       01  WS-FOUND            PIC X        VALUE "N".
       01  WS-POS              PIC 9(2)     VALUE ZERO.
       01  WS-TOTAL            PIC 9(6)     VALUE ZERO.
       01  WS-HIT-QTY          PIC 9(4)     VALUE ZERO.
       01  WS-I                PIC 9(2)     VALUE ZERO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM LOAD-TABLE
           ACCEPT WS-TARGET
           SET WS-IDX TO 1
           SEARCH WS-ENTRY
               AT END
                   MOVE "N" TO WS-FOUND
               WHEN WS-CODE(WS-IDX) = WS-TARGET
                   MOVE "Y" TO WS-FOUND
                   MOVE WS-QTY(WS-IDX) TO WS-HIT-QTY
           END-SEARCH
           SET WS-POS TO WS-IDX
           PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > 5
               ADD WS-QTY(WS-I) TO WS-TOTAL
           END-PERFORM
           DISPLAY "FOUND  " WS-FOUND
           DISPLAY "POS    " WS-POS
           DISPLAY "HITQTY " WS-HIT-QTY
           DISPLAY "TOTAL  " WS-TOTAL
           DISPLAY "THIRD [" WS-CODE(3) "]"
           STOP RUN.
       LOAD-TABLE.
           MOVE "AAA" TO WS-CODE(1)
           MOVE 0120  TO WS-QTY(1)
           MOVE "BBB" TO WS-CODE(2)
           MOVE 0045  TO WS-QTY(2)
           MOVE "CCC" TO WS-CODE(3)
           MOVE 1300  TO WS-QTY(3)
           MOVE "DDD" TO WS-CODE(4)
           MOVE 0007  TO WS-QTY(4)
           MOVE "EEE" TO WS-CODE(5)
           MOVE 0888  TO WS-QTY(5).
