# # backend/profile_manual.py
# from fastapi import APIRouter, Depends
# from pydantic import BaseModel, Field
# from typing import Optional, List,Literal
# from sqlalchemy.ext.asyncio import AsyncSession
# from backend.deps import get_user_from_token    # ok now, because app.py won't import this file
# from backend.db import get_db
# from backend import crud

# router = APIRouter(prefix="/me/manual", tags=["profile-manual"])

# class Sizes(BaseModel):
#     shirt: Optional[str] = None
#     pant: Optional[str] = None
#     shoe: Optional[str] = None
#     tshirt: Optional[str] = None
#     kurta: Optional[str] = None

# class Measurements(BaseModel):
#     chest: Optional[float] = Field(default=None, gt=0)
#     waist: Optional[float] = Field(default=None, gt=0)
#     hip: Optional[float] = Field(default=None, gt=0)

# class ManualIn(BaseModel):
#     sizes: Optional[Sizes] = None
#     fit: Optional[str] = None
#     style: Optional[List[str]] = Field(default=None, min_items=1)
#     colors: Optional[List[str]] = Field(default=None, min_items=1)
#     price_min: Optional[int] = Field(default=None, ge=0)
#     price_max: Optional[int] = Field(default=None, ge=0)
#     preferred_store: Optional[str] = None
#     city: Optional[str] = None
#     brand_prefs: Optional[List[str]] = Field(default=None, min_items=1)
#     notify_channel: Optional[str] = Field(default=None, pattern=r"^(web|telegram|email|sms)$")
#     measurements: Optional[Measurements] = None
#     gender: Optional[Literal["male","female","non_binary","prefer_not_to_say","other"]] = None
    
    

# class KeysIn(BaseModel):
#     keys: List[str] = Field(min_items=1)


# @router.get("")
# async def get_my_manual_profile(user=Depends(get_user_from_token), db: AsyncSession = Depends(get_db)):
#     return await crud.get_manual_profile_with_user(db, user["user_id"])
# # @router.get("/")
# # async def get_manual(user_id: str = Depends(get_user_from_token), db: AsyncSession = Depends(get_db)):
# #     r = await crud.get_manual_profile(db, user_id)
# #     if not r:
# #         return {}
# #     return {
# #         "user_id": user_id,
# #         "sizes": r.sizes,
# #         "fit": r.fit,
# #         "style": r.style,
# #         "colors": r.colors,
# #         "price_min": r.price_min,
# #         "price_max": r.price_max,
# #         "preferred_store": r.preferred_store,
# #         "city": r.city,
# #         "brand_prefs": r.brand_prefs,
# #         "notify_channel": r.notify_channel,
# #         "measurements": r.measurements,
# #         "gender": r.gender,
# #         "updated_at": str(r.updated_at),
        
# #     }

# @router.put("/")
# async def upsert_manual(payload: ManualIn, user_id: str = Depends(get_user_from_token), db: AsyncSession = Depends(get_db)):
#     patch = payload.model_dump(exclude_none=True)
#     if "sizes" in patch:
#         patch["sizes"] = payload.sizes.model_dump(exclude_none=True)
#     if "measurements" in patch:
#         patch["measurements"] = payload.measurements.model_dump(exclude_none=True)
#     return await crud.upsert_manual_profile(db, user_id, patch)

# @router.delete("/")
# async def delete_manual(payload: KeysIn, user_id: str = Depends(get_user_from_token), db: AsyncSession = Depends(get_db)):
#     return await crud.delete_manual_keys(db, user_id, payload.keys)




from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from backend.deps import get_user_from_token
from backend.db import get_db
from backend import crud

router = APIRouter(prefix="/me/manual", tags=["profile-manual"])

class Sizes(BaseModel):
    shirt: Optional[str] = None
    pant: Optional[str] = None
    shoe: Optional[str] = None
    tshirt: Optional[str] = None
    kurta: Optional[str] = None

class Measurements(BaseModel):
    chest: Optional[float] = Field(default=None, gt=0)
    waist: Optional[float] = Field(default=None, gt=0)
    hip: Optional[float] = Field(default=None, gt=0)

# Keep literals in sync with frontend ("non-binary" has a hyphen)
class ManualIn(BaseModel):
    sizes: Optional[Sizes] = None
    fit: Optional[str] = None
    style: Optional[List[str]] = None
    colors: Optional[List[str]] = None
    price_min: Optional[int] = Field(default=None, ge=0)
    price_max: Optional[int] = Field(default=None, ge=0)
    preferred_store: Optional[str] = None
    city: Optional[str] = None
    brand_prefs: Optional[List[str]] = None
    notify_channel: Optional[Literal["web","telegram","email","sms"]] = None
    gender: Optional[Literal["male","female","non-binary","prefer-not-to-say","other"]] = None
    measurements: Optional[Measurements] = None

class KeysIn(BaseModel):
    keys: List[str] = Field(min_items=1)

@router.get("")
async def get_my_manual_profile(user_id: str = Depends(get_user_from_token),
                                db: AsyncSession = Depends(get_db)):
    return await crud.get_manual_profile_with_user(db, user_id)

@router.put("")
async def upsert_manual(payload: ManualIn,
                        user_id: str = Depends(get_user_from_token),
                        db: AsyncSession = Depends(get_db)):
    patch = payload.model_dump(exclude_none=True)
    if "sizes" in patch:
        patch["sizes"] = payload.sizes.model_dump(exclude_none=True)
    if "measurements" in patch:
        patch["measurements"] = payload.measurements.model_dump(exclude_none=True)
    return await crud.upsert_manual_profile(db, user_id, patch)

@router.delete("")
async def delete_manual(payload: KeysIn,
                        user_id: str = Depends(get_user_from_token),
                        db: AsyncSession = Depends(get_db)):
    return await crud.delete_manual_keys(db, user_id, payload.keys)
