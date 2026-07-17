from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from backend.database import get_db
from backend.models import User, Order, Shipment, Warehouse

router = APIRouter(prefix="/logistics", tags=["Logistics"])

@router.get("/shipments")
def get_shipments_list(db: Session = Depends(get_db)):
    """List all shipments for the selector dropdown"""
    try:
        shipments = db.query(Shipment).order_by(Shipment.shipment_id.desc()).all()
        # If no shipments exist in the DB, return a mock demo shipment
        if not shipments:
            return {
                "success": True,
                "demo_mode": True,
                "shipments": [
                    {"shipment_id": 1, "carrier_name": "DHL Express AWS Carrier", "tracking_number": "AWS-DHL-990812-IN"}
                ]
            }
        
        return {
            "success": True,
            "shipments": [
                {
                    "shipment_id": s.shipment_id, 
                    "carrier_name": s.carrier_name, 
                    "tracking_number": s.tracking_number
                } for s in shipments
            ]
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/shipment/{shipment_id}")
def get_shipment(shipment_id: int, db: Session = Depends(get_db)):
    """Get Shipment, Warehouse, and Order dropoffs for Mapping"""
    try:
        shipment = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
        
        # Fallback to offline mock data if shipment not found (matching original python server)
        if not shipment:
            if shipment_id == 1:
                return {
                    "success": True,
                    "demo_mode": True,
                    "shipment": {
                        "shipment_id": 1,
                        "carrier_name": "DHL Express AWS Carrier",
                        "tracking_number": "AWS-DHL-990812-IN",
                        "shipping_cost": 210.50,
                        "estimated_delivery": datetime.now().isoformat()
                    },
                    "warehouse": {
                        "warehouse_id": 101,
                        "name": "Tambaram AWS Hub",
                        "address": "Tambaram, Chennai, Tamil Nadu, 600045",
                        "latitude": 12.931842,
                        "longitude": 80.099549
                    },
                    "dropoffs": [
                        {
                            "order_id": 1001,
                            "buyer_name": "Arun Kumar",
                            "address": "No. 56, Paper Mills Road, Perambur, Chennai, Tamil Nadu"
                        },
                        {
                            "order_id": 1002,
                            "buyer_name": "Siddharth Sen",
                            "address": "Zone 8 Anna Nagar, Chennai, Tamil Nadu"
                        },
                        {
                            "order_id": 1003,
                            "buyer_name": "Kavitha Raj",
                            "address": "Adyar, Chennai, Tamil Nadu"
                        }
                    ]
                }
            return {"success": False, "message": f"Shipment #{shipment_id} not found."}
        
        warehouse = db.query(Warehouse).filter(Warehouse.warehouse_id == shipment.warehouse_id).first()
        orders = db.query(Order).filter(Order.shipment_id == shipment_id).all()
        
        dropoffs_list = []
        for o in orders:
            buyer_email = o.buyer.email if o.buyer else f"Buyer #{o.buyer_id}"
            buyer_name = buyer_email.split('@')[0].capitalize()
            
            # Fallback mock addresses for demo if missing
            address_str = o.delivery_address
            if not address_str:
                addresses_pool = [
                    "No. 56, Paper Mills Road, Perambur, Chennai, Tamil Nadu",
                    "Zone 8 Anna Nagar, Chennai, Tamil Nadu",
                    "Adyar, Chennai, Tamil Nadu",
                    "Guindy, Chennai, Tamil Nadu",
                    "Tambaram, Chennai, Tamil Nadu"
                ]
                address_str = addresses_pool[o.order_id % len(addresses_pool)]
                
            dropoffs_list.append({
                "order_id": o.order_id,
                "buyer_name": buyer_name,
                "address": address_str,
                "latitude": float(o.latitude) if o.latitude else None,
                "longitude": float(o.longitude) if o.longitude else None,
                "total_amount": float(o.total_amount),
                "status": o.global_status
            })

        return {
            "success": True,
            "shipment": {
                "shipment_id": shipment.shipment_id,
                "carrier_name": shipment.carrier_name,
                "tracking_number": shipment.tracking_number,
                "shipping_cost": float(shipment.shipping_cost) if shipment.shipping_cost else 0,
                "estimated_delivery": shipment.estimated_delivery.isoformat() if shipment.estimated_delivery else None
            },
            "warehouse": {
                "warehouse_id": warehouse.warehouse_id if warehouse else shipment.warehouse_id,
                "name": warehouse.location_name if warehouse else "AWS Main Hub",
                "address": warehouse.address if warehouse and warehouse.address else "Tambaram, Chennai, Tamil Nadu",
                "latitude": float(warehouse.latitude) if warehouse and warehouse.latitude else None,
                "longitude": float(warehouse.longitude) if warehouse and warehouse.longitude else None
            },
            "dropoffs": dropoffs_list
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
