from typing import Dict, Any, Type, Optional
from loguru import logger
from pydantic import BaseModel, ValidationError

class SchemaRegistry:
    """
    Solves Fragile Maintenance by separating business logic from execution engine.
    Acts as a central registry for all data structures and API contracts.
    """
    _schemas: Dict[str, Type[BaseModel]] = {}

    @classmethod
    def register(cls, name: str, schema_class: Type[BaseModel]):
        """Register a new schema contract."""
        if name in cls._schemas:
            logger.warning(f"Schema {name} is already registered. Overwriting.")
        cls._schemas[name] = schema_class
        logger.info(f"Registered schema contract: {name}")

    @classmethod
    def get_schema(cls, name: str) -> Optional[Type[BaseModel]]:
        return cls._schemas.get(name)

    @classmethod
    def validate_and_parse(cls, name: str, data: Dict[str, Any]) -> Optional[BaseModel]:
        """
        Validates raw data against the central registry contract.
        Returns the structured object or raises ValueError.
        """
        schema_class = cls.get_schema(name)
        if not schema_class:
            raise ValueError(f"Schema {name} not found in registry.")
        
        try:
            return schema_class(**data)
        except ValidationError as e:
            logger.error(f"Schema validation failed for {name}: {e}")
            raise ValueError(f"Data does not conform to {name} contract.")

# Standard default schemas
class StandardTicket(BaseModel):
    id: str
    issue: str
    priority: int
    customer_id: str

class EmailStandard(BaseModel):
    sender: str
    subject: str
    body: str
    is_urgent: bool

class PRCodeReview(BaseModel):
    pr_url: str
    repo_name: str
    focus_areas: list[str] = ["security", "performance", "best_practices"]
    strict_mode: bool = False

# Auto-register core schemas
SchemaRegistry.register("ticket", StandardTicket)
SchemaRegistry.register("email", EmailStandard)
SchemaRegistry.register("pr_review", PRCodeReview)
