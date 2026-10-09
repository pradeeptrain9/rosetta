      *> Amortisation schedule. The output is one line per month, so an
      *> error in month three is visible and every later line is wrong too.
      *> Gotcha 1: WS-INT has no ROUNDED, so each month's interest is
      *>           truncated before it is accumulated. The total interest
      *>           is therefore NOT the rounded sum of the exact values.
      *> Gotcha 2: the final payment is clamped to the remaining balance,
      *>           so the last line differs from every other line.
      *> Gotcha 3: the loop runs WS-TERM times, which comes from stdin, so
      *>           the output line COUNT is input dependent.
      *> The rate arrives as integer BASIS POINTS, because ACCEPT into a
      *> V-scaled field reads stdin as an integer and would deliver zero.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LOANAMORT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PRIN             PIC 9(7)V99  VALUE ZERO.
       01  WS-RATE-BP          PIC 9(4)     VALUE ZERO.
       01  WS-RATE             PIC 9V9(4)   VALUE ZERO.
       01  WS-TERM             PIC 9(2)     VALUE ZERO.
       01  WS-PMT              PIC 9(7)V99  VALUE ZERO.
       01  WS-BAL              PIC 9(7)V99  VALUE ZERO.
       01  WS-INT              PIC 9(7)V99  VALUE ZERO.
       01  WS-PRINPAY          PIC 9(7)V99  VALUE ZERO.
       01  WS-TOTINT           PIC 9(7)V99  VALUE ZERO.
       01  WS-M                PIC 9(2)     VALUE ZERO.
       01  WS-M-OUT            PIC Z9.
       01  WS-I-OUT            PIC Z(6)9.99.
       01  WS-B-OUT            PIC Z(6)9.99.
       01  WS-P-OUT            PIC Z(6)9.99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-PRIN
           ACCEPT WS-RATE-BP
           ACCEPT WS-TERM
           COMPUTE WS-RATE = WS-RATE-BP / 10000
           IF WS-TERM < 1
               MOVE 1 TO WS-TERM
           END-IF
           IF WS-TERM > 24
               MOVE 24 TO WS-TERM
           END-IF
           MOVE WS-PRIN TO WS-BAL
           COMPUTE WS-PMT ROUNDED = WS-PRIN / WS-TERM
           MOVE WS-PMT TO WS-P-OUT
           DISPLAY "PAYMENT " WS-P-OUT
           PERFORM VARYING WS-M FROM 1 BY 1 UNTIL WS-M > WS-TERM
               PERFORM ONE-MONTH
           END-PERFORM
           MOVE WS-TOTINT TO WS-I-OUT
           MOVE WS-BAL    TO WS-B-OUT
           DISPLAY "TOTINT  " WS-I-OUT
           DISPLAY "ENDBAL  " WS-B-OUT
           STOP RUN.
       ONE-MONTH.
           COMPUTE WS-INT = WS-BAL * WS-RATE / 12
           ADD WS-INT TO WS-TOTINT
           MOVE WS-PMT TO WS-PRINPAY
           IF WS-PRINPAY > WS-BAL
               MOVE WS-BAL TO WS-PRINPAY
           END-IF
           SUBTRACT WS-PRINPAY FROM WS-BAL
           MOVE WS-M   TO WS-M-OUT
           MOVE WS-INT TO WS-I-OUT
           MOVE WS-BAL TO WS-B-OUT
           DISPLAY "M" WS-M-OUT " INT " WS-I-OUT " BAL " WS-B-OUT.
