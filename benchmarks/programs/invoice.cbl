      *> Line pricing with a discount and an edited, signed total.
      *> Gotcha 1: WS-LINE-NET is PIC 9(5)V99 and silently loses the
      *>           high-order digit when quantity x price overflows it.
      *> Gotcha 2: the output picture carries a trailing CR for credits.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INVOICE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-QTY              PIC 9(4)     VALUE ZERO.
       01  WS-UNIT-PRICE       PIC 9(5)V99 VALUE ZERO.
       01  WS-DISC-PCT         PIC 9(2)     VALUE ZERO.
       01  WS-LINE-GROSS       PIC 9(7)V99 VALUE ZERO.
       01  WS-DISCOUNT         PIC 9(7)V99 VALUE ZERO.
       01  WS-LINE-NET         PIC 9(5)V99 VALUE ZERO.
       01  WS-VAT              PIC 9(7)V99 VALUE ZERO.
       01  WS-TOTAL            PIC S9(7)V99 VALUE ZERO.
       01  WS-GROSS-OUT        PIC ZZ,ZZZ,ZZ9.99.
       01  WS-NET-OUT          PIC ZZ,ZZ9.99.
       01  WS-TOTAL-OUT        PIC ZZ,ZZZ,ZZ9.99CR.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-QTY
           ACCEPT WS-UNIT-PRICE
           ACCEPT WS-DISC-PCT
           COMPUTE WS-LINE-GROSS = WS-QTY * WS-UNIT-PRICE
           COMPUTE WS-DISCOUNT   = WS-LINE-GROSS * WS-DISC-PCT / 100
           SUBTRACT WS-DISCOUNT FROM WS-LINE-GROSS GIVING WS-LINE-NET
           COMPUTE WS-VAT ROUNDED = WS-LINE-NET * 0.20
           COMPUTE WS-TOTAL = WS-LINE-NET + WS-VAT
           MOVE WS-LINE-GROSS TO WS-GROSS-OUT
           MOVE WS-LINE-NET   TO WS-NET-OUT
           MOVE WS-TOTAL      TO WS-TOTAL-OUT
           DISPLAY "GROSS " WS-GROSS-OUT
           DISPLAY "NET   " WS-NET-OUT
           DISPLAY "TOTAL " WS-TOTAL-OUT
           STOP RUN.
