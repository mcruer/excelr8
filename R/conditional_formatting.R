add_conditional_formatting <- function (wb, sheet, col_start, col_end, row_start,
                                        row_end, rule, fontColour, bgFill){
  openxlsx::conditionalFormatting(wb,
                        sheet = sheet,
                        cols = col_start:col_end,
                        rows = row_start:row_end,
                        rule = rule,
                        style = openxlsx::createStyle(
                          fontColour = fontColour,
                          bgFill = bgFill
                        ))
  invisible (wb)
}
