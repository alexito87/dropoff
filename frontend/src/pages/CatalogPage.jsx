import { useEffect, useState } from 'react'
import { apiGet } from '../api/client'

export default function CatalogPage() {
  const [categories, setCategories] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadCategories() {
      try {
        const data = await apiGet('/api/v1/categories')
        setCategories(data)
      } catch (e) {
        setError(e.message)
      }
    }
    loadCategories()
  }, [])

  return (
    <div className="page">
      <h1>Каталог</h1>
      <p>Сейчас здесь только каркас MVP. Ниже — категории из backend.</p>
      {error && <div className="alert error">{error}</div>}
      <div className="card">
        <ul>
          {categories.map((category) => (
            <li key={category.id}>{category.name}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}
