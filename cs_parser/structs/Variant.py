from .Base import Base

class Variant(Base):
  def __init__(self, full_name: str, wear_from: str, wear_to: str, wear_name: str, kind: str):
    super().__init__(full_name)
    self.full_name: str | None = full_name
    self.wear_from: str | None = wear_from
    self.wear_to: str | None = wear_to
    self.wear_name: str | None = wear_name 
    self.kind: str | None = kind

  def asdict(self) -> dict:
    return {
      "full_name": self.full_name,
      "wear_from": self.wear_from,
      "wear_to": self.wear_to,
      "wear_name": self.wear_name,
      "kind": self.kind
    }