import axios from "axios"
import { env } from "@/config/env"

export const apiClient = axios.create({
  baseURL: env.apiBaseUrl,
  headers: { Accept: "application/json" },
  withCredentials: false,
})
