## code to prepare `temp` dataset goes here

library(tidyverse)
library(readxl)

template <- read_excel("data-raw/raw/worksheet_template.xlsx")%>%
  #filter (column.name == "project.id") %>%
  #filter (sheet.number == 2) %>%
  mutate(data.length = replace_na(data.length, 5))


xls_col <- function(col_number) {
  if (col_number < 1) {
    stop("Column number must be greater than or equal to 1")
  }

  col_name <- ""

  while (col_number > 0) {
    remainder <- (col_number - 1) %% 26
    col_name <- paste0(base::LETTERS[remainder + 1], col_name)
    col_number <- (col_number - remainder - 1) %/% 26
  }

  return(col_name)
}

xls <- function (column.name, sheet.number, column.number, data.start.row, data.length) {

  var.name <- ensym(var.name) %>% as.character

  paste0(xls_col(column.number),
         data.start.row:(data.start.row + data.length - 1))
}

generate_xls_formula <- function (text, data.start.row, data.length, column.name) {

  text %>%
    build(column.name,
          ~str_replace(., .x, str_c("{xls(", .x, ")}"))) %>%
    glue::glue()

}

xls (project.id, 2, 1, 2, 3)

usethis::use_data(temp, overwrite = TRUE)


temp.fun <- function(a, b, c, d){
  a + b + c
}

tibble(a = 1:3, b = c(1, 0, 1), c = 4:2) %>%
  pmap (temp.fun)







