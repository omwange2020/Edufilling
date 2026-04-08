"""
xml_generator.py
Generates the KRA iTax XML file and packages it into a ZIP.
Format reverse-engineered from real submission: 08-04-2026_17-08-06_A003330907D_ITR.zip
"""

import zipfile
import io
import hashlib
from datetime import datetime


def _fmt(value) -> str:
    """Format a numeric value — strip trailing .0 for whole numbers."""
    if value is None or value == "":
        return ""
    try:
        f = float(str(value).replace(",", ""))
        # Return as integer string if whole number, else as float
        if f == int(f):
            return str(int(f))
        else:
            return str(f)
    except (ValueError, TypeError):
        return str(value)


def _compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_xml(data: dict) -> str:
    """
    Build the KRA iTax XML from the return data dict.

    Expected data keys:
      pin, returnType, periodFrom (YYYY-MM-DD), periodTo (YYYY-MM-DD),
      hasWithholding (bool), hasOtherIncome (bool),
      p9Data: { employerPin, employerName, taxYear, taxablePay,
                pension, payeAuto, mprValue },
      whtData (optional): { grossAmount, taxWithheld }
    """
    p9 = data.get("p9Data", {})
    wht = data.get("whtData", {})
    has_wht = data.get("hasWithholding", False)

    pin = data.get("pin", "")

    # Parse period dates
    period_from = data.get("periodFrom", "")  # YYYY-MM-DD
    period_to = data.get("periodTo", "")      # YYYY-MM-DD

    def fmt_date(d: str) -> str:
        """Convert YYYY-MM-DD → DD/MM/YYYY"""
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return d

    ret_start = fmt_date(period_from)
    ret_end = fmt_date(period_to)

    # Extract year from period
    try:
        ret_year = period_to.split("-")[0]
        deposit_start_year = str(int(ret_year) - 1)
    except Exception:
        ret_year = "2025"
        deposit_start_year = "2024"

    # Compute rolling years for XML header
    yr = int(ret_year)
    last_year = yr - 1
    sec_last = yr - 2
    third_last = yr - 3
    fourth_last = yr - 4
    fifth_last = yr - 5
    sixth_last = yr - 6
    seventh_last = yr - 7
    eighth_last = yr - 8
    ninth_last = yr - 9

    # Audit cert date = 30/06 of year after return year
    audit_cert_date = f"30/06/{yr + 1}"
    audit_start_date = f"01/01/{yr + 1}"

    # P9 values
    taxable_pay = _fmt(p9.get("taxablePay", "0"))
    pension = _fmt(p9.get("pension", "0"))
    paye_auto = _fmt(p9.get("payeAuto", "0"))
    mpr_value = _fmt(p9.get("mprValue", "0"))
    employer_pin = p9.get("employerPin", "P051098084N")
    employer_name = p9.get("employerName", "Teachers Service Commission")

    # Computed values
    try:
        tax_payable_on_salary = float(paye_auto) + float(mpr_value)
        tax_payable_str = _fmt(tax_payable_on_salary)
    except Exception:
        tax_payable_str = "0"

    # WHT values
    gross_amount = _fmt(wht.get("grossAmount", "0")) if has_wht else "0"
    tax_withheld = _fmt(wht.get("taxWithheld", "0")) if has_wht else "0"

    # Return type
    return_type = data.get("returnType", "Original")

    # Business income flag
    declare_bus = "Yes" if has_wht else "No"
    declare_bus_code = "Y" if has_wht else "N"

    # Net taxable employment income = taxable_pay - pension
    try:
        net_taxable_emp = float(taxable_pay) - float(pension)
        net_taxable_emp_str = _fmt(net_taxable_emp)
    except Exception:
        net_taxable_emp_str = "0"

    # Net taxable income = net_taxable_emp - mpr_value (personal relief)
    try:
        net_taxable_income = float(net_taxable_emp_str) - float(mpr_value)
        net_taxable_income_str = _fmt(net_taxable_income)
    except Exception:
        net_taxable_income_str = "0"

    # Tax refund = paye_auto - (tax_payable_on_salary - mpr_value)
    # Actually: refund = credits - tax_payable
    # From real file: TaxPayableS = 99347.11 (computed by KRA), credits = 61876.5
    # We store what we know; KRA recomputes tax payable server-side
    try:
        refund = float(paye_auto) - (float(paye_auto) + float(mpr_value) - float(mpr_value))
        # Simpler: just pass 0, KRA computes this
        refund_str = "0"
    except Exception:
        refund_str = "0"

    # Total deductions = pension
    total_ded = pension

    # Section B (WHT only) — Gross turnover from consultancy
    pla_gto_con = gross_amount if has_wht else "0"

    # Balance sheet placeholders for WHT balancing
    bal_other_ast = "1" if has_wht else ""
    bal_other_loan = "1" if has_wht else ""

    # ── Build SingleCellValue ──────────────────────────────────────────────────
    fields = [
        ("templateInfo.tempVrsn", "19.0.3"),
        ("templateInfo.obligId", "2"),
        ("templateInfo.tempType", "XLS"),
        ("templateInfo.ofcVrsn", "EXCEL 1997-2003"),
        ("RetInf.PIN", pin),
        ("RetInf.LastYear", str(last_year)),
        ("RetInf.SecLastYear", str(sec_last)),
        ("RetInf.ThirdLastYear", str(third_last)),
        ("RetInf.FourthLastYear", str(fourth_last)),
        ("RetInf.FifthLastYear", str(fifth_last)),
        ("templateInfo.moduleId", "2"),
        ("templateInfo.formId", "9"),
        ("RetInf.RetType", return_type),
        ("RetInf.DepositStartDate", f"01/01/{deposit_start_year}"),
        ("RetInf.SixthLastYear", str(sixth_last)),
        ("RetInf.SeventhLastYear", str(seventh_last)),
        ("RetInf.EighthLastYear", str(eighth_last)),
        ("RetInf.NinthLastYear", str(ninth_last)),
        ("RetInf.RetStartDate", ret_start),
        ("RetInf.RtnPrdToActStart", ret_start),
        ("SecA.RtnYear", ret_year),
        ("RetInf.RetEndDate", ret_end),
        ("RetInf.RtnPrdToAct", ret_end),
        ("RetInf.DeclareSelfBusIncome", declare_bus),
        ("RetInf.DeclareSelfBusIncomeCode", declare_bus_code),
        ("dispSec.PartnershipIncome", "No"),
        ("dispSec.EstateTrustIncome", "No"),
        ("dispSec.CarBenefit", "No"),
        ("dispSec.Mortgage", "No"),
        ("dispSec.OwnershipSaving", "No"),
        ("dispSec.InsuRelief", "No"),
        ("dispSec.AdvanceTax", "No"),
        ("dispSec.DTAA", "No"),
        ("RetInf.DeclareExemptionCerti", "No"),
        ("RetInf.DeclareWifeIncome", "No"),
        ("RetInf.SpousePIN", ""),
        ("RetInf.dateforAuditCertificate", audit_cert_date),
        ("RetInf.auditStartDate", audit_start_date),
        ("RetInf.ReturnToDay", "31"),
        ("RetInf.ReturnToDayStr", "st"),
        ("RetInf.DeclareWifeBusIncome", ""),
        ("RetInf.DeclareWifeBusIncomeCode", ""),
        ("RtnInf.MonthCode", "12"),
        ("RetInf.MonthDesc", "December"),
        ("RetInf.DeclareWifeExemptionCerti", ""),
        ("RetInf.YearIncome", ret_year),
        ("BankS", ""), ("BankW", ""),
        ("BankDtl.BankNameS", ""), ("BankDtl.BankNameW", ""),
        ("BranchS", ""), ("BranchW", ""),
        ("BankDtl.BranchNameS", ""), ("BankDtl.BranchNameW", ""),
        ("BankDtl.CityS", ""), ("BankDtl.CityW", ""),
        ("BankDtl.AccNameS", ""), ("BankDtl.AccNameW", ""),
        ("BankDtl.AccNumberS", ""), ("BankDtl.AccNumberW", ""),
        ("audit.PINOfAuditorS", ""), ("audit.PINOfAuditorW", ""),
        ("isAuditAvailable", "N"), ("isAuditAvailableW", "N"),
        ("audit.NameOfAuditorS", ""), ("audit.NameOfAuditorW", ""),
        ("audit.DateOfAuditCertiS", ""), ("audit.DateOfAuditCertiW", ""),
        ("RentPaid.GrossRentalIncomeS", "0"), ("RentPaid.GrossRentalIncomeW", "0"),
        ("RentalIncome.ListSTO", "0"), ("RentalIncome.ListWTO", "0"),
        ("exempt.MonthCodeSMax", "0"), ("exempt.MonthCodeSMin", "0"),
        ("exempt.MonthCodeS", "0"), ("exempt.MonthCodeSJanMar", "0"),
        ("exempt.MonthCodeSAprDec", "0"), ("exempt.MonthCodeSJanJun", "0"),
        ("exempt.MonthCodeSJulDec", "0"), ("exempt.MonthCodeW", "0"),
        ("exempt.MonthCodeWMax", "0"), ("exempt.MonthCodeWMin", "0"),
        ("exempt.MonthCodeWJanMar", "0"), ("exempt.MonthCodeWAprDec", "0"),
        # Section B — P&L (WHT consultancy)
        ("PLA.GrossTurnoverBPRentalToS", "0"),
        ("PLA.GrossTurnoverBPConToS", pla_gto_con),
        ("PLA.OpeningStockS", "0"), ("PLA.PurchasesS", "0"),
        ("PLA.OtherDirectCostsS", "0"), ("PLA.OverHeadsS", "0"),
        ("PLA.deprBussS", ""), ("PLA.deprFarmS", ""), ("PLA.deprRentS", ""),
        ("PLA.deprIntS", ""), ("PLA.deprCommS", ""), ("PLA.deprOtherS", ""),
        ("PLA.ClosingStockS", "0"), ("PLA.OtherIncomeS", "0"),
        ("PLA.ProfitOnDisposalOfAssetsBussS", ""), ("PLA.ProfitOnDisposalOfAssetsFarmS", ""),
        ("PLA.ProfitOnDisposalOfAssetsRentS", ""), ("PLA.ProfitOnDisposalOfAssetsIntS", ""),
        ("PLA.ProfitOnDisposalOfAssetsCommS", ""), ("PLA.ProfitOnDisposalOfAssetsOthS", ""),
        ("PLA.unrealizedExchGainBussS", ""), ("PLA.unrealizedExchGainFarmS", ""),
        ("PLA.unrealizedExchGainRentS", ""), ("PLA.unrealizedExchGainIntS", ""),
        ("PLA.unrealizedExchGainCommS", ""), ("PLA.unrealizedExchGainOthS", ""),
        ("PLA.OperatingExpenseS", "0"), ("PLA.ProvBadDebtsBussS", ""),
        ("PLA.ProvBadDebtsFarmS", ""), ("PLA.ProvBadDebtsRentS", ""),
        ("PLA.ProvBadDebtsIntS", ""), ("PLA.ProvBadDebtsCommS", ""),
        ("PLA.ProvBadDebtsOthS", ""), ("PLA.RentPermisesS", "0"),
        ("PLA.startupCostBussS", ""), ("PLA.startupCostFarmS", ""),
        ("PLA.startupCostRentS", ""), ("PLA.startupCostIntS", ""),
        ("PLA.startupCostCommS", ""), ("PLA.startupCostOthS", ""),
        ("PLA.AdministrativeExpenseS", "0"), ("PLA.deprAdminBussS", ""),
        ("PLA.deprAdminFarmS", ""), ("PLA.deprAdminRentS", ""),
        ("PLA.deprAdminIntS", ""), ("PLA.deprAdminCommS", ""),
        ("PLA.deprAdminOtherS", ""), ("PLA.LossOnDisposalBussS", ""),
        ("PLA.LossOnDisposalFarmS", ""), ("PLA.LossOnDisposalRentS", ""),
        ("PLA.LossOnDisposalIntS", ""), ("PLA.LossOnDisposalCommS", ""),
        ("PLA.LossOnDisposalOtherS", ""), ("PLA.EmploymentExpensesS", "0"),
        ("PLA.RentEmployeeS", "0"), ("PLA.FinancialExpensesS", "0"),
        ("PLA.unrealizedExchLossBussS", ""), ("PLA.unrealizedExchLossFarmS", ""),
        ("PLA.unrealizedExchLossRentS", ""), ("PLA.unrealizedExchLossIntS", ""),
        ("PLA.unrealizedExchLossCommS", ""), ("PLA.unrealizedExchLossOthS", ""),
        ("PLA.OtherExpensesPartIS", "0"),
        ("PLA.ProfitLossBeforeTaxBussS", "0"), ("PLA.ProfitLossBeforeTaxFarmS", "0"),
        ("PLA.ProfitLossBeforeTaxRentS", "0"), ("PLA.ProfitLossBeforeTaxIntS", "0"),
        ("PLA.ProfitLossBeforeTaxCommS", "0"), ("PLA.ProfitLossBeforeTaxOtherS", "0"),
        ("PLA.ProfitLossBeforeTaxS", "0"), ("PLA.finalTaxCarriedToBalanceSheetS", "0"),
        ("PLA.OEBussS", "0"), ("PLA.OEFarmS", "0"), ("PLA.OERentS", "0"),
        ("PLA.OEIntS", "0"), ("PLA.OECommS", "0"), ("PLA.OEOthS", "0"),
        ("PLA.OIBussS", "0"), ("PLA.OIFarmS", "0"), ("PLA.OIRentS", "0"),
        ("PLA.OIIntS", "0"), ("PLA.OICommS", "0"), ("PLA.OIOthS", "0"),
        ("PLA.GrossTurnoverBPRentalToW", "0"), ("PLA.GrossTurnoverBPConToW", "0"),
        ("PLA.OpeningStockW", "0"), ("PLA.PurchasesW", "0"),
        ("PLA.OtherDirectCostsW", "0"), ("PLA.OverHeadsW", "0"),
        ("PLA.deprBussW", ""), ("PLA.deprFarmW", ""), ("PLA.deprRentW", ""),
        ("PLA.deprIntW", ""), ("PLA.deprCommW", ""), ("PLA.deprOtherW", ""),
        ("PLA.ClosingStockW", "0"), ("PLA.OtherIncomeW", "0"),
        ("PLA.ProfitOnDisposalOfAssetsBussW", ""), ("PLA.ProfitOnDisposalOfAssetsFarmW", ""),
        ("PLA.ProfitOnDisposalOfAssetsRentW", ""), ("PLA.ProfitOnDisposalOfAssetsIntW", ""),
        ("PLA.ProfitOnDisposalOfAssetsCommW", ""), ("PLA.ProfitOnDisposalOfAssetsOtherW", ""),
        ("PLA.unrealizedExchGainBussW", ""), ("PLA.unrealizedExchGainFarmW", ""),
        ("PLA.unrealizedExchGainRentW", ""), ("PLA.unrealizedExchGainIntW", ""),
        ("PLA.unrealizedExchGainCommW", ""), ("PLA.unrealizedExchGainOtherW", ""),
        ("PLA.OperatingExpenseW", "0"), ("PLA.ProvBadDebtsBussW", ""),
        ("PLA.ProvBadDebtsFarmW", ""), ("PLA.ProvBadDebtsRentW", ""),
        ("PLA.ProvBadDebtsIntW", ""), ("PLA.ProvBadDebtsCommW", ""),
        ("PLA.ProvBadDebtsOtherW", ""), ("PLA.RentPermisesW", "0"),
        ("PLA.startupCostBussW", ""), ("PLA.startupCostFarmW", ""),
        ("PLA.startupCostRentW", ""), ("PLA.startupCostIntW", ""),
        ("PLA.startupCostCommW", ""), ("PLA.startupCostOthW", ""),
        ("PLA.AdministrativeExpenseW", "0"), ("PLA.deprAdminBussW", ""),
        ("PLA.deprAdminFarmW", ""), ("PLA.deprAdminRentW", ""),
        ("PLA.deprAdminIntW", ""), ("PLA.deprAdminCommW", ""),
        ("PLA.deprAdminOthW", ""), ("PLA.LossOnDisposalBussW", ""),
        ("PLA.LossOnDisposalFarmW", ""), ("PLA.LossOnDisposalRentW", ""),
        ("PLA.LossOnDisposalIntW", ""), ("PLA.LossOnDisposalCommW", ""),
        ("PLA.LossOnDisposalOthW", ""), ("PLA.EmploymentExpensesW", "0"),
        ("PLA.RentEmployeeW", "0"), ("PLA.FinancialExpensesW", "0"),
        ("PLA.unrealizedExchLossBussW", ""), ("PLA.unrealizedExchLossFarmW", ""),
        ("PLA.unrealizedExchLossRentW", ""), ("PLA.unrealizedExchLossIntW", ""),
        ("PLA.unrealizedExchLossCommW", ""), ("PLA.unrealizedExchLossOthW", ""),
        ("PLA.OtherExpensesPartIW", "0"),
        ("PLA.ProfitLossBeforeTaxBussW", "0"), ("PLA.ProfitLossBeforeTaxFarmW", "0"),
        ("PLA.ProfitLossBeforeTaxRentW", "0"), ("PLA.ProfitLossBeforeTaxIntW", "0"),
        ("PLA.ProfitLossBeforeTaxCommW", "0"), ("PLA.ProfitLossBeforeTaxOtherW", "0"),
        ("PLA.ProfitLossBeforeTaxW", "0"), ("PLA.finalTaxCarriedToBalanceSheetW", "0"),
        ("PLA.OEBussW", "0"), ("PLA.OEFarmW", "0"), ("PLA.OERentW", "0"),
        ("PLA.OEIntW", "0"), ("PLA.OECommW", "0"), ("PLA.OEOthW", "0"),
        ("PLA.OIBussW", "0"), ("PLA.OIFarmW", "0"), ("PLA.OIRentW", "0"),
        ("PLA.OIIntW", "0"), ("PLA.OICommW", "0"), ("PLA.OIOthW", "0"),
        # Section C — Balance Sheet
        ("BalSt.TotalFixAstS", "0"), ("BalSt.TotalFixAstW", "0"),
        ("BalSt.LandBuildingS", ""), ("BalSt.LandBuildingW", ""),
        ("BalSt.PlantMachineryS", ""), ("BalSt.PlantMachineryW", ""),
        ("BalSt.MtrVehicleS", ""), ("BalSt.MtrVehicleW", ""),
        ("BalSt.FurnitureFixS", ""), ("BalSt.FurnitureFixW", ""),
        ("BalSt.OtherAstS", bal_other_ast), ("BalSt.OtherAstW", ""),
        ("BalSt.IntangibleAstS", ""), ("BalSt.IntangibleAstW", ""),
        ("BalSt.AccumulatedDeprecnS", ""), ("BalSt.AccumulatedDeprecnW", ""),
        ("BalSt.TotalInvstmntS", "0"), ("BalSt.TotalInvstmntW", "0"),
        ("BalSt.SharesS", ""), ("BalSt.SharesW", ""),
        ("BalSt.DebenturedS", ""), ("BalSt.DebenturedW", ""),
        ("BalSt.FixDepostS", ""), ("BalSt.FixDepostW", ""),
        ("BalSt.GovtSecS", ""), ("BalSt.GovtSecW", ""),
        ("BalSt.OtherInvstmntS", ""), ("BalSt.OtherInvstmntW", ""),
        ("BalSt.TotalCrntAstLoanAdvncS", "0"), ("BalSt.TotalCrntAstLoanAdvncW", "0"),
        ("BalSt.TotalCrntAstS", "0"), ("BalSt.TotalCrntAstW", "0"),
        ("BalSt.TotalInventoryS", "0"), ("BalSt.TotalInventoryW", "0"),
        ("BalSt.StrConsblePckMtrlS", ""), ("BalSt.StrConsblePckMtrlW", ""),
        ("BalSt.RwMaterialS", ""), ("BalSt.RwMaterialW", ""),
        ("BalSt.WorkInProgsS", ""), ("BalSt.WorkInProgsW", ""),
        ("BalSt.FnsTrdGoodS", ""), ("BalSt.FnsTrdGoodW", ""),
        ("BalSt.TotalRcvblDebtorsS", "0"), ("BalSt.TotalRcvblDebtorsW", "0"),
        ("BalSt.TrdRcvDebtrosS", ""), ("BalSt.TrdRcvDebtrosW", ""),
        ("BalSt.PrePaymntS", ""), ("BalSt.PrePaymntW", ""),
        ("BalSt.OtherRcvblDebtorsS", ""), ("BalSt.OtherRcvblDebtorsW", ""),
        ("BalSt.TotalBalAvlblS", "0"), ("BalSt.TotalBalAvlblW", "0"),
        ("BalSt.BankBalS", ""), ("BalSt.BankBalW", ""),
        ("BalSt.CashHndEqupmnS", ""), ("BalSt.CashHndEqupmnW", ""),
        ("BalSt.OtherCrntAstS", ""), ("BalSt.OtherCrntAstW", ""),
        ("BalSt.TotalLoanAdvnceS", "0"), ("BalSt.TotalLoanAdvnceW", "0"),
        ("BalSt.LoanRltPrtyS", ""), ("BalSt.LoanRltPrtyW", ""),
        ("BalSt.LoanAdvncStffS", ""), ("BalSt.LoanAdvncStffW", ""),
        ("BalSt.DepositS", ""), ("BalSt.DepositW", ""),
        ("BalSt.LoanAdvnceOthrS", ""), ("BalSt.LoanAdvnceOthrW", ""),
        ("BalSt.DeferredTxAstS", ""), ("BalSt.DeferredTxAstW", ""),
        ("BalSt.TotalCrntLiabtyPrvsnsS", "0"), ("BalSt.TotalCrntLiabtyPrvsnsW", "0"),
        ("BalSt.TotalCrntLiabtyS", "0"), ("BalSt.TotalCrntLiabtyW", "0"),
        ("BalSt.TradePayblCrdtS", ""), ("BalSt.TradePayblCrdtW", ""),
        ("BalSt.LiabtyLeasAstS", ""), ("BalSt.LiabtyLeasAstW", ""),
        ("BalSt.AccredInterestS", ""), ("BalSt.AccredInterestW", ""),
        ("BalSt.BankOverDrftS", ""), ("BalSt.BankOverDrftW", ""),
        ("BalSt.OtherCrntLiabtyS", ""), ("BalSt.OtherCrntLiabtyW", ""),
        ("BalSt.TotalPrvsnsS", "0"), ("BalSt.TotalPrvsnsW", "0"),
        ("BalSt.PrvsnsIncomeTxS", ""), ("BalSt.PrvsnsIncomeTxW", ""),
        ("BalSt.PrvsnsBadDbtS", ""), ("BalSt.PrvsnsBadDbtW", ""),
        ("BalSt.OtherPrvsnsS", ""), ("BalSt.OtherPrvsnsW", ""),
        ("BalSt.TotalAStS", "0"), ("BalSt.TotalAStW", "0"),
        ("BalSt.TotalProprietorCptlRsvS", "0"), ("BalSt.TotalProprietorCptlRsvW", "0"),
        ("BalSt.ProperietorCptlS", ""), ("BalSt.ProperietorCptlW", ""),
        ("BalSt.RevalustionRsvS", ""), ("BalSt.RevalustionRsvW", ""),
        ("BalSt.TnsltnRsvS", ""), ("BalSt.TnsltnRsvW", ""),
        ("BalSt.GnrlRsvS", ""), ("BalSt.GnrlRsvW", ""),
        ("BalSt.AnyOthrRsvS", ""), ("BalSt.AnyOthrRsvW", ""),
        ("BalSt.ProfitYearS", ""), ("BalSt.ProfitYearW", ""),
        ("BalSt.TotalLoanFundS", "0"), ("BalSt.TotalLoanFundW", "0"),
        ("BalSt.TotalSecurdLaibtyS", "0"), ("BalSt.TotalSecurdLaibtyW", "0"),
        ("BalSt.LoanFinancialInstS", ""), ("BalSt.LoanFinancialInstW", ""),
        ("BalSt.OthrLoanS", bal_other_loan), ("BalSt.OthrLoanW", ""),
        ("BalSt.DbtSecurIssuedS", ""), ("BalSt.DbtSecurIssuedW", ""),
        ("BalSt.DueRltdPartyS", ""), ("BalSt.DueRltdPartyW", ""),
        ("BalSt.TotalUnsecureLaibtyS", "0"), ("BalSt.TotalUnsecureLaibtyW", "0"),
        ("BalSt.UnsecuredLoanFinancialInstS", ""), ("BalSt.UnsecuredLoanFinancialInstW", ""),
        ("BalSt.UnsecuredOtherLoanS", ""), ("BalSt.UnsecuredOtherLoanW", ""),
        ("BalSt.UnsecuredPayblCrdtThnOneS", ""), ("BalSt.UnsecuredPayblCrdtThnOneW", ""),
        ("BalSt.UnsecuredDueRltdPartyS", ""), ("BalSt.UnsecuredDueRltdPartyW", ""),
        ("BalSt.DeferredTxLiabtyS", ""), ("BalSt.DeferredTxLiabtyW", ""),
        ("BalSt.ProprietorFundLngTrmLaibtyS", "0"), ("BalSt.ProprietorFundLngTrmLaibtyW", "0"),
        ("Inv.OpeningStockTOS", "0"), ("Inv.PurchaseTOS", "0"),
        ("Inv.SalesQuantTOS", "0"), ("Inv.ClosingStockTOS", "0"), ("Inv.StorageTOS", "0"),
        ("Inv.OpeningStockTOW", "0"), ("Inv.PurchaseTOW", "0"),
        ("Inv.SalesQuantTOW", "0"), ("Inv.ClosingStockTOW", "0"), ("Inv.StorageTOW", "0"),
        ("Inv.OpeningStockKIITOS", "0"), ("Inv.PurchaseKIITOS", "0"),
        ("Inv.ConsKIITOS", "0"), ("Inv.SalesQuantKIITOS", "0"),
        ("Inv.ClosingStockKIITOS", "0"), ("Inv.YieldKIITOS", "0"), ("Inv.StorageKIITOS", "0"),
        ("Inv.OpeningStockKIITOW", "0"), ("Inv.PurchaseKIITOW", "0"),
        ("Inv.ConsKIITOW", "0"), ("Inv.SalesQuantKIITOW", "0"),
        ("Inv.ClosingStockKIITOW", "0"), ("Inv.YieldKIITOW", "0"), ("Inv.StorageKIITOW", "0"),
        ("IniAllPlanMach.CostTOS", "0"), ("IniAllPlanMach.ListPart1IniAllS", "0"),
        ("RetInf.RetPeriodTo", ret_year),
        ("IniAllPlanMach.CostTOW", "0"), ("IniAllPlanMach.ListPart1IniAllW", "0"),
        ("IniAllIBD.CostTOS", "0"), ("IniAllIBD.ListPart2IniAllS", "0"),
        ("IniAllIBD.QualExpeTOS", "0"), ("IniAllIBD.ListPart2ResValTOS", "0"),
        ("IniAllIBD.ListPart2IBDTOS", "0"), ("IniAllIBD.ResiValueTOS", "0"),
        ("IniAllIBD.CostTOW", "0"), ("IniAllIBD.ListPart2IniAllW", "0"),
        ("IniAllIBD.QualExpeTOW", "0"), ("IniAllIBD.ListPart2ResValTOW", "0"),
        ("IniAllIBD.ListPart2IBDTOW", "0"), ("IniAllIBD.ResiValueTOW", "0"),
        ("AgrLandDed.ExpIncTOS", "0"), ("AgrLandDed.WdvTOS", "0"),
        ("AgrLandDed.SalesTransferTOS", "0"), ("AgrLandDed.ListDedS", "0"),
        ("AgrLandDed.WdvAtTheEndTOS", "0"),
        ("AgrLandDed.ExpIncTOW", "0"), ("AgrLandDed.WdvTOW", "0"),
        ("AgrLandDed.SalesTransferTOW", "0"), ("AgrLandDed.ListDedW", "0"),
        ("AgrLandDed.WdvAtTheEndTOW", "0"),
        ("DeprIntengAst.WDVTOS", ""), ("DeprIntengAst.ListDepreS", "0"),
        ("DeprIntengAst.WDVAtTheEndTOS", "0"),
        ("DeprIntengAst.WDVTOW", ""), ("DeprIntengAst.ListDepreW", "0"),
        ("DeprIntengAst.WDVAtTheEndTOW", "0"),
        ("WAT.TotalWATS", "0"), ("WAT.TotalWATW", "0"),
        ("WAT.TotalCostS", "0"), ("WAT.TotalWATB", "0"),
        ("WAT.TotalCostW", "0"), ("WAT.TotalWATListBW", "0"),
        ("CA.ListPart1IniAllS", "0"), ("CA.ListPart1IniAllW", "0"),
        ("CA.ListPart2IniAllS", "0"), ("CA.ListPart2IniAllW", "0"),
        ("CA.ListPart2IBDTOS", "0"), ("CA.ListPart2IBDTOW", "0"),
        ("CA.TotalWATS", "0"), ("CA.TotalWATW", "0"),
        ("CA.TotalWATListBS", "0"), ("CA.TotalWATListBW", "0"),
        ("CA.ListDedS", "0"), ("CA.ListDedW", "0"),
        ("CA.ListDepreS", "0"), ("CA.ListDepreW", "0"),
        ("CapAll.TotalAllAllowancesS", "0"), ("CapAll.TotalAllAllowancesW", "0"),
        # Section F — Employment Income
        ("EmpIncome.ListSTO", taxable_pay),
        ("EmpIncome.ListSTOJANMARLbl", "January - March:  Income"),
        ("EmpIncome.ListSTOJANMAR", "0"),
        ("EmpIncome.ListSTOJanDecSum", "0"),
        ("EmpIncome.ListSPENSJANMARLbl", "January - March:  Pension"),
        ("EmpIncome.ListSPENSJANMAR", "0"),
        ("EmpIncome.ListSTOAPRDECLbl", "April - December:  Income"),
        ("EmpIncome.ListSTOAPRDEC", "0"),
        ("EmpIncome.ListSPENSAPRDECLbl", "April - December:  Pension"),
        ("EmpIncome.ListSPENSAPRDEC", "0"),
        ("EmpIncome.ListSTOJanDecPensionSum", "0"),
        ("EmpIncome.ListWTO", "0"),
        ("ProfitShare.ListSTO", "0"), ("ProfitShare.ListWTO", "0"),
        ("EstateTrust.ListTOS", "0"),
        ("EstateTrust.ListTOSJanMarLbl", "Total Amount of Share Income January -June"),
        ("EstateTrust.ListTOSJanMar", "0"), ("EstateTrust.ListTOW", "0"),
        ("CarBenefit.ListSTO", "0"), ("CarBenefit.ListWTO", "0"),
        ("MortgageIntDtls.ListSTO", "0"),
        ("MortgageIntDtls.ListSTOJANMARLBL", "January - March:  Interest"),
        ("MortgageIntDtls.ListSTOJANMAR", "0"),
        ("MortgageIntDtls.ListSTOJanDecSum", "0"),
        ("MortgageIntDtls.ListSTOAPRDECLBL", "April - December:  Interest"),
        ("MortgageIntDtls.ListSTOAPRDEC", "0"),
        ("MortgageIntDtls.ListWTO", "0"),
        ("HomeOwnershipSavingPlan.ListSTO", "0"),
        ("HomeOwnershipSavingPlan.ListSTOJANMAR", "0"),
        ("HomeOwnershipSavingPlan.ListSTOJanDecSum", "0"),
        ("HomeOwnershipSavingPlan.ListSTOAPRDEC", "0"),
        ("HomeOwnershipSavingPlan.ListWTO", "0"),
        ("InsReliefDtls.ListSTO", "0"), ("PRMFInsuranceTotal", "0"),
        ("AHRInsuranceTotal", "0"), ("OtherInsuranceTotal", "0"),
        ("InsReliefDtls.ListWTO", "0"),
        ("OtherEmpInc.LumpsumGrossInc", ""), ("OtherEmpInc.LumpsumTaxDeduc", ""),
        ("OtherEmpInc.GratuityGrossInc", ""), ("OtherEmpInc.GratuityTaxDeduc", ""),
        ("OtherEmpInc.PensionGrossInc", ""), ("OtherEmpInc.PensionTaxDeduc", ""),
        ("OtherEmpInc.ArrearsGrossInc", ""), ("OtherEmpInc.ArrearsTaxDeduc", ""),
        ("OtherEmpInc.InterestGrossInc", ""), ("OtherEmpInc.InterestTaxDeduc", ""),
        ("OtherEmpInc.DividendsGrossInc", ""), ("OtherEmpInc.DividendsTaxDeduc", ""),
        ("OtherEmpInc.OthersGrossInc", ""), ("OtherEmpInc.OthersTaxDeduc", ""),
        ("EmpIncome2.TotGrossAmt", "0"), ("EmpIncome2.TotTaxDedc", "0"),
        # Section M — PAYE
        ("PayeDed.ListSTO", paye_auto),
        ("PayeDed.ListWTO", "0"),
        ("InstallmentTax.ListSTO", "0"), ("InstallmentTax.ListWTO", "0"),
        # Section T — Withholding
        ("WithHolding.ListSTO", tax_withheld if has_wht else "0"),
        ("WithHolding.ListWTO", "0"),
        ("VehicleAdvTaxPaid.ListSTO", "0"), ("VehicleAdvTaxPaid.ListWTO", "0"),
        ("DtlIncomePaid.IncomePaidAdvanceListSTO", "0"),
        ("DtlIncomePaid.IncomePaidSelfAssmntListSTO", "0"),
        ("DtlIncomePaid.IncomePaidAdvncSelfAssmntListSTO", "0"),
        ("DtlIncomePaid.IncomePaidAdvanceListWTO", "0"),
        ("DtlIncomePaid.IncomePaidSelfAssmntListWTO", "0"),
        ("DtlIncomePaid.IncomePaidAdvncSelfAssmntListWTO", "0"),
        ("DTAEMPIncomeS", "0"), ("DTAACredits.AmountTotalS", "0"),
        ("DTAEMPIncomeSJanMarLbl", "Total Gross Employment Income January -March"),
        ("DTAEMPIncomeSJanMar", "0"), ("DTAEMPIncomeW", "0"),
        ("DTAACredits.AmountTotalW", "0"),
        ("DtlLossFrwd.BussEarlierLossS", "0"), ("DtlLossFrwd.FarmEarlierLossS", "0"),
        ("DtlLossFrwd.RentEarlierLossS", "0"), ("DtlLossFrwd.IntrEarlierLossS", "0"),
        ("DtlLossFrwd.CommEarlierLossS", "0"), ("DtlLossFrwd.OthrEarlierLossS", "0"),
        ("DtlLossFrwd.BussLossAdjustS", ""), ("DtlLossFrwd.FarmLossAdjustS", ""),
        ("DtlLossFrwd.RentLossAdjustS", ""), ("DtlLossFrwd.InterestLossAdjustS", ""),
        ("DtlLossFrwd.CommLossAdjustS", ""), ("DtlLossFrwd.OtherLossAdjustS", ""),
        ("DtlLossFrwd.BussEarlierLossW", "0"), ("DtlLossFrwd.FarmEarlierLossW", "0"),
        ("DtlLossFrwd.RentEarlierLossW", "0"), ("DtlLossFrwd.IntrEarlierLossW", "0"),
        ("DtlLossFrwd.CommEarlierLossW", "0"), ("DtlLossFrwd.OtherEarlierLossW", "0"),
        ("DtlLossFrwd.BussLossAdjustW", ""), ("DtlLossFrwd.FarmLossAdjustW", ""),
        ("DtlLossFrwd.RentLossAdjustW", ""), ("DtlLossFrwd.InterestLossAdjustW", ""),
        ("DtlLossFrwd.CommLossAdjustW", ""), ("DtlLossFrwd.OtherLossAdjustW", ""),
        ("TaxComp.chargeableIncomePartS", "0"),
        ("TC.BussTaxableIncomeS", "0"), ("TC.FarmTaxableIncomeS", "0"),
        ("TC.RentTaxableIncomeS", "0"), ("TC.IntrTaxableIncomeS", "0"),
        ("TC.CommTaxableIncomeS", "0"), ("TC.OtherTaxableIncomeS", "0"),
        ("TC.TotalTaxableIncomeConsdtS", "0"),
        ("TaxComp.BUSSLossCurrentYrIncomeS", "0"), ("TaxComp.FARMLossCurrentYrIncomeS", "0"),
        ("TaxComp.RENTLossCurrentYrIncomeS", "0"), ("TaxComp.INTRLossCurrentYrIncomeS", "0"),
        ("TaxComp.COMMLossCurrentYrIncomeS", "0"), ("TaxComp.OTHRLossCurrentYrIncomeS", "0"),
        ("TC.TotalLossCurrntYrIncomeConsdtS", "0"),
        ("TaxComp.ChargeableIncomeS", "0"),
        ("TaxComp.OEBussS", "0"), ("TaxComp.OEFarmS", "0"), ("TaxComp.OERentS", "0"),
        ("TaxComp.OEIntS", "0"), ("TaxComp.OECommS", "0"), ("TaxComp.OEOthS", "0"),
        ("TaxComp.ODBussS", "0"), ("TaxComp.ODFarmS", "0"), ("TaxComp.ODRentS", "0"),
        ("TaxComp.ODIntS", "0"), ("TaxComp.ODCommS", "0"), ("TaxComp.ODOthS", "0"),
        ("TaxComp.chargeableIncomePartW", "0"),
        ("TC.BussTaxableIncomeW", "0"), ("TC.FarmTaxableIncomeW", "0"),
        ("TC.RentTaxableIncomeW", "0"), ("TC.IntrTaxableIncomeW", "0"),
        ("TC.CommTaxableIncomeW", "0"), ("TC.OtherTaxableIncomeW", "0"),
        ("TC.TotalTaxableIncomeConsdtW", "0"),
        ("TaxComp.BUSSLossCurrentYrIncomeW", "0"), ("TaxComp.FARMLossCurrentYrIncomeW", "0"),
        ("TaxComp.RENTLossCurrentYrIncomeW", "0"), ("TaxComp.INTRLossCurrentYrIncomeW", "0"),
        ("TaxComp.COMMLossCurrentYrIncomeW", "0"), ("TaxComp.OTHRLossCurrentYrIncomeW", "0"),
        ("TC.TotalLossCurrntYrIncomeConsdtW", "0"),
        ("TaxComp.ChargeableIncomeW", "0"),
        ("TaxComp.OEBussW", "0"), ("TaxComp.OEFarmW", "0"), ("TaxComp.OERentW", "0"),
        ("TaxComp.OEIntW", "0"), ("TaxComp.OECommW", "0"), ("TaxComp.OEOthW", "0"),
        ("TaxComp.ODBussW", "0"), ("TaxComp.ODFarmW", "0"), ("TaxComp.ODRentW", "0"),
        ("TaxComp.ODIntW", "0"), ("TaxComp.ODCommW", "0"), ("TaxComp.ODOthW", "0"),
        ("IncomeSplit.GrossIncomeJanJune", "0"), ("IncomeSplit.SumGrossIncomeJanDec", "0"),
        ("IncomeSplit.AllowExpeJanJune", "0"), ("IncomeSplit.TaxableIncomeJanJune", "0"),
        ("IncomeSplit.SumTaxableIncomeJanDec", "0"),
        ("IncomeSplit.GrossIncomeJulyDec", "0"), ("IncomeSplit.AllowExpeJulyDec", "0"),
        ("IncomeSplit.TaxableIncomeJulyDec", "0"),
        # Section T — Deductions
        ("DedDtl.TotalDeductionS", pension),
        ("DedDtl.TotalDeductionW", "0"),
        ("DedDtl.TotalDeductionSJanMar", "0"), ("DedDtl.TotalDeductionWJanMar", "0"),
        ("DedDtl.PensionS", pension), ("DedDtl.PensionW", ""),
        ("MortgageJanMar2020Self", "0"),
        ("TaxComp.Mortgage", "Mortgage Interest  (Total of Amount of Interest Paid from J_Computation_of_Mortgage)"),
        ("TaxComp.MortgageIntDtlsListSTO", "0"),
        ("TaxCopm.MortgageIntDtlsListWTO", "0"),
        ("MortgageJanMar2020Wife", "0"),
        ("TaxComp.HomeOwnershipSavingPlanListSTO", "0"),
        ("TaxComp.HomeOwnershipSavingPlanListWTO", "0"),
        ("HospJanMar2020Self", "0"),
        ("DedDtl.PRMFS", "0"), ("DedDtl.AHLS", ""), ("DedDtl.SHIFS", "0"),
        ("HospJanMar2020Wife", "0"),
        ("TaxComp.TotTaxableIncomeLessRlfS", mpr_value),
        ("TaxComp.TotTaxableIncomeLessRlfW", "0"),
        ("TaxComp.EmpIncomeListSTO", taxable_pay),
        ("TaxComp.EmpIncomeListWTO", "0"),
        ("TaxComp.NetTaxableEmpIncomeSJanDec", net_taxable_emp_str),
        ("TaxComp.TaxbleIncomeEstateS", "0"), ("TaxComp.TaxbleIncomeEstateW", "0"),
        ("TaxComp.NetTaxableEmpIncomeWJanDec", "0"),
        ("TaxComp.ExemptedAmtS", "0"), ("TaxComp.ExemptedAmtW", "0"),
        ("TaxComp.ExemptedAmtSJanMar", "0"),
        ("TaxComp.NetTaxableIncomeS", net_taxable_income_str),
        ("TaxComp.NetTaxableIncomeW", "0.00"),
        ("TaxComp.ExemptedAmtSAprDec", "0"),
        ("TaxComp.TaxPayableS", tax_payable_str),
        ("TaxComp.TaxPayableW", "0"),
        ("TaxComp.ExemptedAmtWJanMar", "0"),
        ("TaxComp.TaxPayableSJanMarLbl", "Tax on Taxable Employment Income January -March Period"),
        ("TaxComp.TaxPayableSJanMar", "0"), ("TaxComp.TaxPayableWJanMar", "0"),
        ("TaxComp.ExemptedAmtWAprDec", "0"),
        ("TaxComp.TaxPayableSAprDecLbl", "Tax on Taxable Employment Income April -December Period"),
        ("TaxComp.TaxPayableSAprDec", "0"), ("TaxComp.TaxPayableWAprDec", "0"),
        ("TaxComp.PersonalReliefS", mpr_value), ("TaxComp.PersonalReliefW", "0"),
        ("TaxComp.InsReliefDtlsListSTO", "0"), ("TaxComp.InsReliefDtlsListWTO", "0"),
        ("CreditIncome.TotalTaxCreditS", paye_auto),
        ("CreditIncome.TotalTaxCreditW", "0"),
        ("TaxComp.PayeDedListSTO", paye_auto), ("TaxComp.PayeDedListWTO", "0"),
        ("TaxComp.EstateTrustListTOS", "0"), ("TaxComp.EstateTrustListTOW", "0"),
        ("TaxComp.InstallmentTaxListSTO", "0"), ("TaxComp.InstallmentTaxListWTO", "0"),
        ("TaxComp.WithHoldingListSTO", tax_withheld if has_wht else "0"),
        ("TaxComp.WithHoldingListWTO", "0"),
        ("TaxComp.VehicleAdvTaxPaidListSTO", "0"), ("TaxComp.VehicleAdvTaxPaidListWTO", "0"),
        ("TaxComp.IncomePaidAdvanceListSTO", "0"), ("TaxComp.IncomePaidAdvanceListWTO", "0"),
        ("TaxComp.IncomeDTACreditsS", "0"), ("TaxComp.IncomeDTACreditsW", "0"),
        ("TaxComp.MRI", "0"), ("TaxComp.MRIWTO", "0"),
        ("FinalTax.TaxRefundDueS", refund_str), ("FinalTax.TaxRefundDueW", "0"),
    ]

    single_cell_value = "@P_@".join(f"{k}%V_@{v}" for k, v in fields)

    # ── Build MultiCellValue ───────────────────────────────────────────────────
    # WAT rates row (fixed)
    wat_row = "WAT.ListS@PL@25%VL@10%VL@25%VL@12.5%VL@%VL@rateH%VL@H@PL@%VL@%VL@%VL@%VL@0%VL@balBDH%VL@H@PL@%VL@%VL@%VL@%VL@0%VL@curAstVH%VL@H@PL@%VL@%VL@%VL@%VL@0%VL@salesH%VL@H@PL@0%VL@0%VL@0%VL@0%VL@0%VL@balWATH%VL@H@PL@0%VL@0%VL@0%VL@0%VL@0%VL@WATH%VL@H@PL@0%VL@0%VL@0%VL@0%VL@0%VL@balCDH%VL@H"

    # Section F row: PIN, Name, GrossPay, 0, 0, 0, "", GrossPay
    emp_row = f"EmpIncome.ListS@PL@{employer_pin}%VL@{employer_name}%VL@{taxable_pay}%VL@0%VL@0%VL@0%VL@%VL@{taxable_pay}%VL@H"

    # Section M row: PIN, Name, TaxablePay, TaxPayable, PAYEAuto, MPRValue
    paye_row = f"PayeDed.ListS@PL@{employer_pin}%VL@{employer_name}%VL@{taxable_pay}%VL@{tax_payable_str}%VL@{paye_auto}%VL@{mpr_value}%VL@H"

    # Fixed empty PLA rows (required by KRA)
    pla_empty = "%VL@".join(["0", "", "", "0", "0", "", "", "", "0", "", "", "", "0", "", "", "0", "", "", "", "", "", "", "0", "", "", "", "0", "0", "", "", "", "", "", "", "", "", "", "", "0", "0", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "0", "0", "", "", "", "", "0", "", "", "", "", "", "", "", "", "", "0", "", "", "", "", "", "", "0", "0", "", "", ""])
    pla_rows = [
        f"PLA.BussIncomeDataS@PL@{pla_empty}PLABUSSH",
        f"PLA.FarmIncomeDataS@PL@{pla_empty}PLAFARMH",
        f"PLA.RentIncomeDataS@PL@{pla_empty}PLARENTH",
        f"PLA.IntIncomeDataS@PL@{pla_empty}PLAINTH",
        f"PLA.CommIncomeDataS@PL@{pla_empty}PLACOMMH",
        f"PLA.OthIncomeDataS@PL@{pla_empty}PLAOTHRH",
    ]

    # Consolidate row (all zeros)
    zeros_94 = "%VL@".join(["0"] * 93 + ["", "0"])
    pla_cnsl = f"PLA.ConsolidateDataS@PL@{zeros_94}PLACNSLH"

    # Tax computation rows (all zeros — KRA computes)
    zeros_32 = "%VL@".join(["0"] * 5 + ["", "", "0", "", "", "0", "", "0", "", "", "", "0", "0", "0", "", "", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0"])
    tax_rows = [
        f"TaxComp.BussinessListS@PL@{zeros_32}TAXBUSSH",
        "TaxComp.CnslListS@PL@" + "%VL@".join(["0"]*31) + "TAXCNSLH",
        f"TaxComp.CommListS@PL@{zeros_32}TAXCOMMH",
        f"TaxComp.FarmListS@PL@{zeros_32}TAXFARMH",
        f"TaxComp.IntListS@PL@{zeros_32}TAXINTH",
        f"TaxComp.OthListS@PL@{zeros_32}TAXOTHRH",
        f"TaxComp.RentListS@PL@{zeros_32}TAXRENTH",
    ]

    # Loss forward rows
    loss_empty = "%VL@".join([""] * 9 + ["0", "", "0", "0", "0"])
    loss_rows = [
        f"DtlLossFrwd.BussinessS@PL@{loss_empty}LOSSBUSH",
        f"DtlLossFrwd.FarmingS@PL@{loss_empty}LOSSFRMH",
        f"DtlLossFrwd.RentalS@PL@{loss_empty}LOSSRNTH",
        f"DtlLossFrwd.InterestS@PL@{loss_empty}LOSSINTH",
        f"DtlLossFrwd.CommissionS@PL@{loss_empty}LOSSCOMH",
        f"DtlLossFrwd.OtherS@PL@{loss_empty}LOSSOTHH",
        "DtlLossFrwd.TotalS@PL@" + "%VL@".join(["0"]*14) + "LOSSTOTH",
    ]

    dtaa_row = "DTAACredits.DetailsS@PL@%VL@%VL@%VL@%VL@%VL@%VL@H@PL@%VL@%VL@%VL@%VL@%VL@%VL@H"

    all_multi_rows = (
        [wat_row, emp_row, paye_row]
        + pla_rows
        + [pla_cnsl]
        + tax_rows
        + loss_rows
        + [dtaa_row]
    )
    multi_cell_value = "@L_@".join(all_multi_rows)

    # ── Compute hashes ─────────────────────────────────────────────────────────
    single_hash = _compute_hash(single_cell_value)
    multi_hash = _compute_hash(multi_cell_value)

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\r\n'
        '<Sheet>\r\n'
        f'<SingleCellValue>{single_cell_value}</SingleCellValue>\r\n'
        f'<MultiCellValue>{multi_cell_value}</MultiCellValue>\r\n'
        f'<SingleCellHash>{single_hash}</SingleCellHash>\r\n'
        f'<MultiCellHash>{multi_hash}</MultiCellHash>\r\n'
        '<SheetCode>ITR_RET</SheetCode>\r\n'
        '</Sheet>'
    )
    return xml


def generate_itr_zip(data: dict) -> tuple[bytes, str]:
    """
    Generate the KRA ITR XML and package it as a ZIP.
    Returns (zip_bytes, zip_filename).
    Filename format: DD-MM-YYYY_HH-MM-SS_PIN_ITR.zip
    """
    now = datetime.now()
    timestamp = now.strftime("%d-%m-%Y_%H-%M-%S")
    pin = data.get("pin", "UNKNOWN")
    base_name = f"{timestamp}_{pin}_ITR"
    xml_filename = f"{base_name}.xml"
    zip_filename = f"{base_name}.zip"

    xml_content = build_xml(data)
    xml_bytes = xml_content.encode("utf-8")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(xml_filename, xml_bytes)
    zip_buffer.seek(0)

    return zip_buffer.read(), zip_filename
