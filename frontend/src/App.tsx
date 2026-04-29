import { Routes, Route } from 'react-router-dom'
import RunsList from './pages/RunsList'
import RunDetail from './pages/RunDetail'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RunsList />} />
      <Route path="/runs/:id" element={<RunDetail />} />
    </Routes>
  )
}
