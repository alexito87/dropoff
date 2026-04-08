import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPatch, apiPost, apiUpload } from '../api/client'

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const MAX_FILE_SIZE = 5 * 1024 * 1024
const MAX_FILES = 5

const emptyForm = {
  category_id: '',
  title: '',
  description: '',
  daily_price_cents: 0,
  deposit_cents: 0,
  city: '',
  pickup_address: '',
}

export default function ItemFormPage() {
  const { itemId } = useParams()
  const navigate = useNavigate()
  const isEdit = Boolean(itemId)

  const [form, setForm] = useState(emptyForm)
  const [categories, setCategories] = useState([])
  const [images, setImages] = useState([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [uploadErrors, setUploadErrors] = useState([])
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [itemStatus, setItemStatus] = useState('draft')

  useEffect(() => {
    async function bootstrap() {
      const categoriesData = await apiGet('/api/v1/categories')
      setCategories(categoriesData)

      if (isEdit) {
        const item = await apiGet(`/api/v1/items/${itemId}`, true)
        setForm({
          category_id: item.category_id,
          title: item.title,
          description: item.description,
          daily_price_cents: item.daily_price_cents,
          deposit_cents: item.deposit_cents,
          city: item.city,
          pickup_address: item.pickup_address,
        })
        setImages(item.images || [])
        setItemStatus(item.status)
      }
    }

    bootstrap().catch((e) => setError(e.message))
  }, [isEdit, itemId])

  const remainingSlots = useMemo(() => Math.max(MAX_FILES - images.length, 0), [images.length])
  const isEditable = itemStatus === 'draft' || itemStatus === 'rejected'

  function updateField(name, value) {
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  async function handleSave(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setMessage('')

    try {
      if (isEdit) {
        await apiPatch(`/api/v1/items/${itemId}`, form, true)

        if (!images.length) {
          setMessage('Черновик сохранён. Добавьте хотя бы одно фото и нажмите «Сохранить объявление» ещё раз для отправки на модерацию.')
          return
        }

        await apiPost(`/api/v1/items/${itemId}/submit-for-moderation`, {}, true)
        setMessage('Объявление отправлено на модерацию')
        navigate('/my-items')
      } else {
        const created = await apiPost('/api/v1/items', form, true)
        navigate(`/my-items/${created.id}/edit`, {
          state: {
            successMessage:
              'Черновик сохранён. Добавьте хотя бы одно фото и нажмите «Сохранить объявление» ещё раз для отправки на модерацию.',
          },
        })
      }
    } catch (e) {
      const normalized = String(e.message || '')
      if (
        normalized.includes('Field required') ||
        normalized.includes('Input should') ||
        normalized.includes('valid')
      ) {
        setError('Для добавления объявления заполните обязательные поля')
      } else if (normalized.includes('At least one image is required')) {
        setError('Добавьте хотя бы одно изображение')
      } else {
        setError(normalized)
      }
    } finally {
      setSaving(false)
    }
  }

  async function handleFilesSelected(fileList) {
    const files = Array.from(fileList || [])
    if (!files.length || !itemId || !isEditable) return

    setUploadErrors([])
    setMessage('')
    setError('')

    const currentErrors = []
    const validFiles = []

    for (const file of files.slice(0, remainingSlots)) {
      if (!ACCEPTED_TYPES.includes(file.type)) {
        currentErrors.push(`${file.name}: неподдерживаемый формат`)
        continue
      }
      if (file.size > MAX_FILE_SIZE) {
        currentErrors.push(`${file.name}: файл больше 5 MB`)
        continue
      }
      validFiles.push(file)
    }

    if (files.length > remainingSlots) {
      currentErrors.push(`Можно загрузить максимум ${MAX_FILES} изображений на объявление`)
    }

    setUploadErrors(currentErrors)
    if (!validFiles.length) return

    setUploading(true)
    try {
      const results = []
      for (const file of validFiles) {
        try {
          const uploaded = await apiUpload(`/api/v1/items/${itemId}/images`, file, true)
          results.push(uploaded)
        } catch (e) {
          currentErrors.push(`${file.name}: ${e.message}`)
        }
      }
      if (results.length) {
        setImages((prev) => [...prev, ...results])
      }
      setUploadErrors([...currentErrors])
    } finally {
      setUploading(false)
    }
  }

  async function handleDeleteImage(imageId) {
    if (!isEditable) return

    setError('')
    setMessage('')
    try {
      await apiDelete(`/api/v1/items/${itemId}/images/${imageId}`, true)
      setImages((prev) => prev.filter((image) => image.id !== imageId))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1>{isEdit ? 'Редактировать объявление' : 'Создать объявление'}</h1>
          <p className="muted">
            После сохранения объявление отправляется на модерацию, если заполнены обязательные поля и добавлено хотя бы одно фото.
          </p>
        </div>
        <button className="button ghost" type="button" onClick={() => navigate('/my-items')}>
          Назад к списку
        </button>
      </div>

      {!isEditable && (
        <div className="alert">
          Это объявление нельзя редактировать в текущем статусе: {itemStatus}
        </div>
      )}

      <form className="card item-form-card" onSubmit={handleSave}>
        <label>
          Категория
          <select
            value={form.category_id}
            onChange={(e) => updateField('category_id', e.target.value)}
            required
            disabled={!isEditable}
          >
            <option value="">Выбери категорию</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Название
          <input
            value={form.title}
            onChange={(e) => updateField('title', e.target.value)}
            required
            disabled={!isEditable}
          />
        </label>

        <label>
          Описание
          <textarea
            value={form.description}
            onChange={(e) => updateField('description', e.target.value)}
            rows={6}
            required
            disabled={!isEditable}
          />
        </label>

        <div className="form-grid-two">
          <label>
            Цена за день, в копейках
            <input
              type="number"
              min="0"
              value={form.daily_price_cents}
              onChange={(e) => updateField('daily_price_cents', Number(e.target.value))}
              required
              disabled={!isEditable}
            />
          </label>
          <label>
            Депозит, в копейках
            <input
              type="number"
              min="0"
              value={form.deposit_cents}
              onChange={(e) => updateField('deposit_cents', Number(e.target.value))}
              required
              disabled={!isEditable}
            />
          </label>
        </div>

        <label>
          Город
          <input
            value={form.city}
            onChange={(e) => updateField('city', e.target.value)}
            required
            disabled={!isEditable}
          />
        </label>

        <label>
          Адрес самовывоза
          <input
            value={form.pickup_address}
            onChange={(e) => updateField('pickup_address', e.target.value)}
            required
            disabled={!isEditable}
          />
        </label>

        {message && <div className="alert success">{message}</div>}
        {error && <div className="alert error">{error}</div>}

        {isEditable && (
          <button className="button" disabled={saving}>
            {saving ? 'Сохраняем...' : 'Сохранить объявление'}
          </button>
        )}
      </form>

      {isEdit && (
        <div className="card item-images-card">
          <h2>Изображения</h2>
          <p className="muted">
            Допустимые форматы: JPEG, PNG, WebP. Максимум 5 MB на файл, максимум 5 файлов.
          </p>

          {isEditable && (
            <label className={`upload-dropzone ${uploadErrors.length ? 'error' : ''}`}>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                disabled={uploading || remainingSlots === 0}
                onChange={(e) => handleFilesSelected(e.target.files)}
              />
              <span>
                {uploading
                  ? 'Загружаем...'
                  : remainingSlots === 0
                    ? 'Достигнут лимит 5 изображений'
                    : 'Нажми или перетащи файлы сюда'}
              </span>
            </label>
          )}

          {uploadErrors.length > 0 && (
            <div className="alert error">
              {uploadErrors.map((value) => (
                <div key={value}>{value}</div>
              ))}
            </div>
          )}

          <div className="image-grid">
            {images.map((image) => (
              <div className="image-card" key={image.id}>
                <img src={image.url} alt="Изображение объявления" />
                {isEditable && (
                  <button
                    className="button danger"
                    type="button"
                    onClick={() => handleDeleteImage(image.id)}
                  >
                    Удалить
                  </button>
                )}
              </div>
            ))}
            {!images.length && <div className="muted">Изображений пока нет</div>}
          </div>
        </div>
      )}
    </div>
  )
}
