      *> One value through five report pictures.
      *> Gotcha 1: a floating currency string $$$,$$9.99 puts the sign
      *>           character immediately left of the first significant
      *>           digit, so its POSITION moves with the magnitude.
      *> Gotcha 2: check protection *** fills suppressed positions with
      *>           asterisks, not spaces.
      *> Gotcha 3: BLANK WHEN ZERO blanks the ENTIRE field, commas and
      *>           decimal point included.
      *> Gotcha 4: DB and CR print only for a negative value and occupy
      *>           two trailing bytes either way.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CURRENCY.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-AMT              PIC S9(7)V99 VALUE ZERO.
       01  WS-FLOAT-CUR        PIC $$$,$$9.99.
       01  WS-CHECK-PROT       PIC ***,**9.99.
       01  WS-BLANK-ZERO       PIC ZZZ,ZZ9.99 BLANK WHEN ZERO.
       01  WS-DEBIT            PIC ZZZ,ZZ9.99DB.
       01  WS-CREDIT           PIC ZZZ,ZZ9.99CR.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-AMT
           MOVE WS-AMT TO WS-FLOAT-CUR
           MOVE WS-AMT TO WS-CHECK-PROT
           MOVE WS-AMT TO WS-BLANK-ZERO
           MOVE WS-AMT TO WS-DEBIT
           MOVE WS-AMT TO WS-CREDIT
           DISPLAY "CUR   [" WS-FLOAT-CUR "]"
           DISPLAY "PROT  [" WS-CHECK-PROT "]"
           DISPLAY "BLANK [" WS-BLANK-ZERO "]"
           DISPLAY "DEBIT [" WS-DEBIT "]"
           DISPLAY "CRED  [" WS-CREDIT "]"
           STOP RUN.
