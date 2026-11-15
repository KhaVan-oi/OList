import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { MainLayout } from './components/layouts'
import { CustomerPaymentPage } from './features/customer-payment'
import { DssPage } from './features/dss'
import { OverviewPage } from './features/overview'
import { ProductGeoPage } from './features/product-geo'
import { SalesTimePage } from './features/sales-time'
import { SellerPage } from './features/seller'
import { QueryProvider } from './providers/query-provider'

export default function App() {
  return (
    <QueryProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<MainLayout />}>
            <Route index element={<OverviewPage />} />
            <Route path="thoi-gian" element={<SalesTimePage />} />
            <Route path="hang-hoa" element={<ProductGeoPage />} />
            <Route path="seller" element={<SellerPage />} />
            <Route path="khach" element={<CustomerPaymentPage />} />
            <Route path="quyet-dinh" element={<DssPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryProvider>
  )
}
