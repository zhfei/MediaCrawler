# -*- coding: utf-8 -*-

from typing import Any

from pydantic import BaseModel, Field


class GoogleMapsPoint(BaseModel):
    city: str = Field(..., description="采集点城市")
    address: str = Field(default="", description="采集点地址")
    country: str = Field(default="BR", description="采集点国家")
    lat: float = Field(..., description="采集点纬度")
    lng: float = Field(..., description="采集点经度")


class GoogleMapsTask(BaseModel):
    task_id: str = Field(..., description="任务ID")
    point: GoogleMapsPoint = Field(..., description="采集点位")
    keyword: str = Field(..., description="采集关键词")
    status: str = Field(default="pending", description="任务状态")
    retry_count: int = Field(default=0, description="重试次数")
    last_error: str = Field(default="", description="最后错误")


class GoogleMapsShop(BaseModel):
    keyword: list[str] = Field(default_factory=list, description="命中关键词集合")
    platform: str = Field(default="GoogleMap", description="平台")
    city: str = Field(default="", description="城市")
    shop_id: str = Field(default="", description="Google Maps 店铺ID")
    shop_name: str = Field(default="", description="店铺名称")
    level: float | None = Field(default=None, description="评分")
    category: list[str] = Field(default_factory=list, description="品类")
    is_open: str = Field(default="", description="营业状态原文")
    shop_lat: float | None = Field(default=None, description="店铺纬度")
    shop_lng: float | None = Field(default=None, description="店铺经度")
    crawl_lat: float | None = Field(default=None, description="采集点纬度")
    crawl_lng: float | None = Field(default=None, description="采集点经度")
    address: str = Field(default="", description="地址")
    phone: str = Field(default="", description="电话")
    order_url: str = Field(default="", description="下单URL")
    official_url: str = Field(default="", description="官网URL")
    user_ratings_total: int = Field(default=0, description="评论数")
    avg_price: str = Field(default="", description="原始人均消费")
    open_hours: list[Any] = Field(default_factory=list, description="营业时间")
    report_count: int = Field(default=1, description="召回次数")
    menu_url: str = Field(default="", description="菜单URL")
    service_options: list[str] = Field(default_factory=list, description="服务项")
    busy_time: str = Field(default="", description="繁忙时间")
    create_time: str = Field(default="", description="创建时间")
    real_shop_state: str = Field(default="正常营业", description="店铺状态")
    currency_symbol: str = Field(default="", description="货币符号")
    price_range: str = Field(default="", description="价格带")
    consumption_level: str = Field(default="", description="消费等级")
    detail_url: str = Field(default="", description="Google Maps 详情链接")
