      *> In-place bubble sort over an OCCURS table. No SORT verb.
      *> Gotcha 1: the single ACCEPT sits inside a loop, so the program
      *>           consumes EIGHT lines of stdin from one ACCEPT statement.
      *>           A tool that counts ACCEPT statements to size its test
      *>           input will feed this program one line and seven EOFs.
      *> Gotcha 2: the outer loop bound shrinks each pass, and the swap
      *>           counter is part of the output, so an equivalent port has
      *>           to perform the SAME comparisons in the SAME order.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BUBBLESORT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-LIST.
           05  WS-NUM OCCURS 8 TIMES PIC 9(4).
       01  WS-I                PIC 9(2)     VALUE ZERO.
       01  WS-J                PIC 9(2)     VALUE ZERO.
       01  WS-LIMIT            PIC 9(2)     VALUE ZERO.
       01  WS-TMP              PIC 9(4)     VALUE ZERO.
       01  WS-SWAPS            PIC 9(3)     VALUE ZERO.
       01  WS-PASSES           PIC 9(3)     VALUE ZERO.
       01  WS-LINE             PIC X(40)    VALUE SPACES.
       01  WS-PTR              PIC 9(3)     VALUE 1.
       01  WS-N-OUT            PIC Z(3)9.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > 8
               ACCEPT WS-NUM(WS-I)
           END-PERFORM
           MOVE 7 TO WS-LIMIT
           PERFORM UNTIL WS-LIMIT < 1
               ADD 1 TO WS-PASSES
               PERFORM VARYING WS-J FROM 1 BY 1
                       UNTIL WS-J > WS-LIMIT
                   IF WS-NUM(WS-J) > WS-NUM(WS-J + 1)
                       MOVE WS-NUM(WS-J)     TO WS-TMP
                       MOVE WS-NUM(WS-J + 1) TO WS-NUM(WS-J)
                       MOVE WS-TMP           TO WS-NUM(WS-J + 1)
                       ADD 1 TO WS-SWAPS
                   END-IF
               END-PERFORM
               SUBTRACT 1 FROM WS-LIMIT
           END-PERFORM
           MOVE 1 TO WS-PTR
           MOVE SPACES TO WS-LINE
           PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > 8
               MOVE WS-NUM(WS-I) TO WS-N-OUT
               STRING WS-N-OUT DELIMITED BY SIZE
                      "," DELIMITED BY SIZE
                   INTO WS-LINE
                   WITH POINTER WS-PTR
               END-STRING
           END-PERFORM
           DISPLAY "SORTED [" WS-LINE "]"
           DISPLAY "SWAPS   " WS-SWAPS
           DISPLAY "PASSES  " WS-PASSES
           DISPLAY "MIN     " WS-NUM(1)
           DISPLAY "MAX     " WS-NUM(8)
           STOP RUN.
