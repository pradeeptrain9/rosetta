      *> Progressive tax with a ROUNDED store next to a truncated one.
      *> Gotcha 1: WS-TAX uses ROUNDED (half up), WS-NET does not.
      *> Gotcha 2: EVALUATE falls through to the last WHEN OTHER branch.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-GROSS            PIC 9(6)V99 VALUE ZERO.
       01  WS-DEPENDENTS       PIC 9(2)     VALUE ZERO.
       01  WS-RATE             PIC 9V9(4)  VALUE ZERO.
       01  WS-TAXABLE          PIC 9(6)V99 VALUE ZERO.
       01  WS-TAX              PIC 9(6)V99 VALUE ZERO.
       01  WS-NET              PIC 9(6)V99 VALUE ZERO.
       01  WS-ALLOWANCE        PIC 9(5)V99 VALUE ZERO.
       01  WS-TAX-OUT          PIC Z(5)9.99.
       01  WS-NET-OUT          PIC Z(5)9.99.
       01  WS-BRACKET          PIC X(8)     VALUE SPACES.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-GROSS
           ACCEPT WS-DEPENDENTS
           COMPUTE WS-ALLOWANCE = WS-DEPENDENTS * 450
           IF WS-ALLOWANCE > WS-GROSS
               MOVE ZERO TO WS-TAXABLE
           ELSE
               SUBTRACT WS-ALLOWANCE FROM WS-GROSS GIVING WS-TAXABLE
           END-IF
           PERFORM PICK-BRACKET
           COMPUTE WS-TAX ROUNDED = WS-TAXABLE * WS-RATE
           SUBTRACT WS-TAX FROM WS-GROSS GIVING WS-NET
           MOVE WS-TAX TO WS-TAX-OUT
           MOVE WS-NET TO WS-NET-OUT
           DISPLAY "BRACKET " WS-BRACKET
           DISPLAY "TAX     " WS-TAX-OUT
           DISPLAY "NET     " WS-NET-OUT
           STOP RUN.
       PICK-BRACKET.
           EVALUATE TRUE
               WHEN WS-TAXABLE < 1000
                   MOVE 0.0000 TO WS-RATE
                   MOVE "EXEMPT"   TO WS-BRACKET
               WHEN WS-TAXABLE < 4000
                   MOVE 0.1200 TO WS-RATE
                   MOVE "LOW"      TO WS-BRACKET
               WHEN WS-TAXABLE < 9000
                   MOVE 0.2450 TO WS-RATE
                   MOVE "MIDDLE"   TO WS-BRACKET
               WHEN OTHER
                   MOVE 0.3375 TO WS-RATE
                   MOVE "TOP"      TO WS-BRACKET
           END-EVALUATE.
