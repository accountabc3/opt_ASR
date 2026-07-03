from dataclasses import asdict, dataclass, field

@dataclass
class ResourcePlan:
    plan_id: str
    task_semantics: dict
    evidence_binding: dict
    surface_realization: dict
    n_instances: int = 1
    plan_role: str = ""
    def to_flat_dict(self) -> dict:
        return {
            "G": self.task_semantics.get("G", ""),
            "A": self.task_semantics.get("A", ""),
            "C": self.task_semantics.get("C", ""),
            "S": self.evidence_binding.get("S", ""),
            "E": self.evidence_binding.get("E", ""),
            "T": self.surface_realization.get("T", ""),
            "L": self.surface_realization.get("L", ""),
            "R": self.surface_realization.get("R", ""),
        }

@dataclass
class ScheduledBlock:
    module_id: str
    block_id: str
    role: str
    required: bool = True

@dataclass
class PlanSchedule:
    plan_id: str
    genre: str
    resource_type: str
    ordered_blocks: list[ScheduledBlock] = field(default_factory=list)
    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "genre": self.genre,
            "resource_type": self.resource_type,
            "ordered_blocks": [asdict(block) for block in self.ordered_blocks],
        }

@dataclass
class BlockSpec:
    plan_id: str
    resource_type: str
    blocks: list[dict] = field(default_factory=list)
    def to_dict(self) -> dict:
        modules = []
        seen = set()
        for block in self.blocks:
            module_id = block.get("module_id", "")
            if module_id and module_id not in seen:
                modules.append(module_id)
                seen.add(module_id)
        return {
            "plan_id": self.plan_id,
            "resource_type": self.resource_type,
            "modules": modules,
            "blocks": self.blocks,
        }
