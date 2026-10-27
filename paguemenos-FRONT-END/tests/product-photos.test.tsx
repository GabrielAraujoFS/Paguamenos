import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, expect, it } from "vitest"
import { apiClient } from "@/api/client"
import { getProductImageUrl } from "@/api/services/products"
import { ProductCard } from "@/features/catalog/ProductCard"
import type { Product } from "@/contracts/api"

const products: Product[] = [
  { id: "syn-001", name: "Sabonete Brisa", category: "higiene", description: "Sabonete corporal fictício de uso diário.", price: "8.90", authorized_offer: "Oferta autorizada" },
  { id: "syn-002", name: "Shampoo Aurora", category: "cabelos", description: "Shampoo fictício para limpeza dos cabelos.", price: "24.50", authorized_offer: "Oferta autorizada" },
  { id: "syn-003", name: "Hidratante Nuvem", category: "cuidados pessoais", description: "Loção corporal fictícia.", price: "32.90", authorized_offer: "Oferta autorizada" },
  { id: "syn-004", name: "Escova Sorriso", category: "higiene bucal", description: "Escova dental fictícia de cerdas macias.", price: "12.00", authorized_offer: "Oferta autorizada" },
  { id: "syn-005", name: "Algodão Sereno", category: "acessórios", description: "Algodão fictício para cuidados pessoais.", price: "6.75", authorized_offer: "Oferta autorizada" },
  { id: "syn-006", name: "Protetor Solar Solara", category: "Proteção solar", description: "Protetor solar facial fictício FPS 50, toque seco, 60 g.", price: "39.90", authorized_offer: "Preço sintético de demonstração, sem desconto adicional." },
]
afterEach(cleanup)

it.each(products)("exibe foto acessível de $name e preserva dados e navegação do cartão", (product) => {
  render(<MemoryRouter><ProductCard product={product} /></MemoryRouter>)
  const photo = screen.getByRole("img", { name: `Fotografia do produto ${product.name}` }) as HTMLImageElement
  expect(photo.getAttribute("src")).toBe(getProductImageUrl(product.id))
  expect(photo.getAttribute("src")).toMatch(new RegExp(`/products/${product.id}/image$`))
  expect(photo.getAttribute("loading")).toBe("lazy")
  expect(photo.classList.contains("object-contain")).toBe(true)
  expect(screen.getByRole("heading", { name: product.name })).toBeTruthy()
  expect(screen.getByText(product.category)).toBeTruthy()
  expect(screen.getByText(product.description)).toBeTruthy()
  expect(screen.getByText(new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(product.price)).replace(/\u00a0/g, " "))).toBeTruthy()
  expect(screen.getByRole("link", { name: "Ver produto" }).getAttribute("href")).toBe(`/products/${product.id}`)
})

it("mostra placeholder sem perder preço, informações ou navegação quando a foto falha", () => {
  const product = products[0]
  render(<MemoryRouter><ProductCard product={product} /></MemoryRouter>)
  fireEvent.error(screen.getByRole("img", { name: `Fotografia do produto ${product.name}` }))
  expect(screen.getByRole("img", { name: `Fotografia indisponível de ${product.name}` })).toBeTruthy()
  expect(screen.getByText("Fotografia indisponível")).toBeTruthy()
  expect(screen.getByText(product.description)).toBeTruthy()
  expect(screen.getByText("R$ 8,90")).toBeTruthy()
  expect(screen.getByRole("link", { name: "Ver produto" })).toBeTruthy()
})

it.each(["/api", "http://127.0.0.1:8000"])("resolve o endereço pela configuração compartilhada %s", (baseURL) => {
  const previous = apiClient.defaults.baseURL
  try {
    apiClient.defaults.baseURL = baseURL
    expect(getProductImageUrl("opaque/id")).toBe(`${baseURL}/products/opaque%2Fid/image`)
  } finally { apiClient.defaults.baseURL = previous }
})
