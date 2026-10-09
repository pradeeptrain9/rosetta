      *> Compound interest accrued year by year.
      *> The rate arrives as an integer number of BASIS POINTS, because
      *> ACCEPT into a V-scaled field reads stdin as an integer and would
      *> silently deliver zero for "0500". Scaling in COBOL instead keeps
      *> the fractional arithmetic - and the trap - reachable.
      *> Gotcha: COMPUTE has no ROUNDED, so each year's interest is
      *> TRUNCATED to two decimals before it is added to the balance.
      *> A port that keeps full precision drifts by cents over 30 years.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INTEREST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PRINCIPAL        PIC 9(7)V99 VALUE ZERO.
       01  WS-RATE-BP          PIC 9(4)     VALUE ZERO.
       01  WS-RATE             PIC 9V9(4)  VALUE ZERO.
       01  WS-YEARS            PIC 9(2)     VALUE ZERO.
       01  WS-BALANCE          PIC 9(9)V99 VALUE ZERO.
       01  WS-INTEREST         PIC 9(9)V99 VALUE ZERO.
       01  WS-TOTAL-INT        PIC 9(9)V99 VALUE ZERO.
       01  WS-BAL-OUT          PIC Z(8)9.99.
       01  WS-INT-OUT          PIC Z(8)9.99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           ACCEPT WS-PRINCIPAL
           ACCEPT WS-RATE-BP
           ACCEPT WS-YEARS
           COMPUTE WS-RATE = WS-RATE-BP / 10000
           MOVE WS-PRINCIPAL TO WS-BALANCE
           PERFORM ACCRUE-YEAR WS-YEARS TIMES
           MOVE WS-BALANCE   TO WS-BAL-OUT
           MOVE WS-TOTAL-INT TO WS-INT-OUT
           DISPLAY "BALANCE  " WS-BAL-OUT
           DISPLAY "INTEREST " WS-INT-OUT
           STOP RUN.
       ACCRUE-YEAR.
           COMPUTE WS-INTEREST = WS-BALANCE * WS-RATE
           ADD WS-INTEREST TO WS-BALANCE
           ADD WS-INTEREST TO WS-TOTAL-INT.
