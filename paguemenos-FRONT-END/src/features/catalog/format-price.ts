export function formatPrice(price: string): string {
  const [integer, cents] = price.split(".")
  if (!integer || cents === undefined) return price
  return `R$ ${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ".")},${cents}`
}
