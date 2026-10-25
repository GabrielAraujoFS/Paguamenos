import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/api/query-keys"
import { getHealth } from "@/api/services/system"

export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: getHealth })
}
