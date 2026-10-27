export const LIST_PAGE_SIZE = 6
export function pageNumber(value) {
  const number = Number(value)
  return Number.isSafeInteger(number) && number > 0 ? number : 1
}
export function paginate(items, requestedPage = 1) {
  const total = items.length
  const pageCount = Math.max(1, Math.ceil(total / LIST_PAGE_SIZE))
  const page = Math.min(pageNumber(requestedPage), pageCount)
  return { page, pageCount, total, pageSize: LIST_PAGE_SIZE,
    items: items.slice((page - 1) * LIST_PAGE_SIZE, page * LIST_PAGE_SIZE) }
}
