% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/helpers.R
\name{apply_styles}
\alias{apply_styles}
\title{Apply Styles to Cells in an Excel Sheet}
\usage{
apply_styles(
  wb,
  sheet.number,
  rows,
  column.number,
  fontName,
  fontSize,
  fontColour,
  numFmt,
  border,
  borderColour,
  borderStyle,
  bgFill,
  fgFill,
  halign,
  valign,
  textDecoration,
  wrapText,
  textRotation,
  indent,
  locked,
  hidden
)
}
\arguments{
\item{wb}{A workbook object from openxlsx.}

\item{sheet.number}{Numeric or character identifier for the sheet.}

\item{rows}{The row range to apply the style to.}

\item{column.number}{The column number to apply the style to.}

\item{fontName}{Font name.}

\item{fontSize}{Font size.}

\item{fontColour}{Font color.}

\item{numFmt}{Number format.}

\item{border}{Border style.}

\item{borderColour}{Border color.}

\item{borderStyle}{Border style.}

\item{bgFill}{Background fill color.}

\item{fgFill}{Foreground fill color.}

\item{halign}{Horizontal alignment.}

\item{valign}{Vertical alignment.}

\item{textDecoration}{Text decoration.}

\item{wrapText}{Wrap text.}

\item{textRotation}{Text rotation angle.}

\item{indent}{Indentation level.}

\item{locked}{Lock cells.}

\item{hidden}{Hide cells.}
}
\value{
NULL. The function modifies the workbook object in place.
}
\description{
This internal function applies styles to a specific range of cells
in an Excel workbook using the openxlsx package.
}
\keyword{internal}
