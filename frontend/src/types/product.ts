export interface ProductItem {
  service_product_code: string
  service_product_name: string
  product_type: string
  category: string
  service_order_type: string
  unit: string
  price: string
  price_status: string
  related_category: string
  related_area: string
  fault_phenomenon: string
  remark: string
}

export interface ProductSearchResult {
  score: number
  service_product_code: string
  service_product_name: string
  service_order_type: string
  product_type: string
  related_area: string
  fault_phenomenon: string
  price: string
  unit: string
}

export interface ProductSearchDiagnosticCandidate {
  service_product_code?: string | null
  service_product_name?: string | null
  service_order_type?: string | null
  fault_phenomenon?: string | null
  vector_score?: number | null
  keyword_overlap?: boolean | null
  fault_keyword_overlap?: boolean | null
  penalty?: number | null
  bonus?: number | null
  adjusted_score?: number | null
  included?: boolean
  filtered_reason?: string | null
}

export interface ProductSearchDiagnostics {
  query: string
  top_k?: number | null
  threshold?: number | null
  has_fault?: boolean
  fetch_k?: number | null
  fallback_to_vector_results?: boolean
  returned_count?: number | null
  returned_codes?: string[]
  reason?: string | null
  candidates?: ProductSearchDiagnosticCandidate[]
}

export interface ProductSearchResponse {
  query: string
  count: number
  products: ProductSearchResult[]
  diagnostics?: ProductSearchDiagnostics | null
}
