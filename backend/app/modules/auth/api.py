<<<<<<< Updated upstream
# пустой файл для модуля auth API
=======
from fastapi import APIRouter

router = APIRouter()

@router.get('/health')
async def health_check():
    return {'status': 'ok'}
>>>>>>> Stashed changes
