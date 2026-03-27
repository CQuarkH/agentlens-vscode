from typing import List, Literal, Optional, Dict
from pydantic import BaseModel, Field, root_validator
import math

# --- Visual Mappings ---
CATEGORY_COLORS: Dict[str, str] = {
    "General": "#94a3b8",      # Slate 400
    "Implementation": "#60a5fa", # Blue 400
    "Build": "#4ade80",         # Green 400
    "Management": "#c084fc",    # Purple 400
    "Quality": "#f87171",       # Red 400
    "Uncategorized": "#e2e8f0"
}

DEFAULT_CATEGORY_COLOR = "#94a3b8"
MUST_COLOR = "#ef4444"
SHOULD_COLOR = "#eab308"
ROOT_COLOR = "#1e293b"


# --- Domain Entities ---

class RuleContent(BaseModel):
    text: str
    originalHeader: str

class RuleMetadata(BaseModel):
    strength: Literal["MUST", "SHOULD"]
    format: Literal["ListItem", "Paragraph"]

class AgentRule(BaseModel):
    """Leaf node representing an actionable rule/instruction."""
    id: str
    type: Literal["rule"] = "rule"
    content: RuleContent
    metadata: RuleMetadata
    
    # Optional parent reference injected during tree building for uniqueness mapping if needed
    parent_id: Optional[str] = None

    @property
    def graph_id(self) -> str:
        if self.parent_id:
            return f"{self.parent_id}_{self.id}"
        return self.id

    @property
    def code_lines(self) -> int:
        """Counts presence of code-like structural markers to determine density, tolerating LLM backtick wiping"""
        text = self.content.text
        count = 0
        if '`' in text:
            return 1
            
        code_indicators = ['()', '[]', '{}', '=', 'src/', '.rs', '.py', '.ts', '.js', '<', '>', '#[']
        for ind in code_indicators:
            if ind in text:
                return 1
                
        return 0

    @property
    def color(self) -> str:
        return SHOULD_COLOR
        
    @property
    def tree_width(self) -> int:
        return 250
        
    @property
    def tree_height(self) -> int:
        return 45

    @property
    def force_graph_radius(self) -> int:
        return 8 if self.metadata.strength == "MUST" else 6
        
    @property
    def tree_graph_radius(self) -> int:
        return 6

    @property
    def short_label(self) -> str:
        text = self.content.text
        return text[:30] + "..." if len(text) > 30 else text
        
    @property
    def html_details(self) -> str:
        return f"""
            {self.content.text}<br><br>
            <hr>
            <small>
            <strong>Original Header:</strong> {self.content.originalHeader}<br>
            <strong>Format:</strong> {self.metadata.format}<br>
            <strong>ID:</strong> {self.id}
            </small>
            """

class RuleLabel(BaseModel):
    """Intermediate node representing a semantic grouping of rules (formerly Category)."""
    id: str
    label: str
    type: Literal["category", "label"] = "label"
    count: int
    children: List[AgentRule] = Field(default_factory=list)
    fre_score: Optional[float] = None
    parent_id: Optional[str] = None

    @property
    def color(self) -> str:
        # Fallback if frontend doesn't override with category lightness modification
        return "#e2e8f0" 
        
    @property
    def total_rules(self) -> int:
        return len(self.children)

    @property
    def code_lines(self) -> int:
        return sum(rule.code_lines for rule in self.children)
        
    @property
    def code_ratio(self) -> float:
        if self.total_rules == 0:
            return 0.0
        return self.code_lines / self.total_rules
        
    @property
    def border_width(self) -> float:
        """Density formulation: 1.5px base + multiplier, max 8px"""
        bw = 1.5 + (self.code_ratio * 1.5)
        return min(bw, 8.0)
        
    @property
    def tree_width(self) -> int:
        """Width = 80 + fre_score. Capped between 80px and 180px."""
        fre = self.fre_score if self.fre_score is not None else 50
        width = 80 + fre
        return max(80, min(180, width))
        
    @property
    def tree_height(self) -> int:
        """Height = 40 + (rules * 10) capped at 120px"""
        height = 40 + (self.total_rules * 10)
        return min(height, 120)

    @property
    def html_details(self) -> str:
        fre_val = round(self.fre_score, 1) if self.fre_score is not None else 'N/A'
        return f"Label: {self.label}<br>Total Rules: {self.count}<br>Code Ratio: {round(self.code_ratio, 2)}<br>FRE Cognitive Load: {fre_val}"

    def inject_parent_ids(self) -> None:
        for rule in self.children:
            rule.parent_id = self.id

class RuleCategory(BaseModel):
    """Macro parent node representing a parent category mapping (General, Implementation, etc)."""
    id: str
    label: str
    type: Literal["category"] = "category"
    count: int = 0
    children: List[RuleLabel] = Field(default_factory=list)

    @property
    def color(self) -> str:
        return CATEGORY_COLORS.get(self.label, DEFAULT_CATEGORY_COLOR)

    @property
    def total_rules(self) -> int:
        return sum(label.total_rules for label in self.children)
        
    @property
    def total_labels(self) -> int:
        return len(self.children)

    @property
    def code_lines(self) -> int:
        return sum(label.code_lines for label in self.children)
        
    @property
    def code_ratio(self) -> float:
        if self.total_rules == 0:
            return 0.0
        return self.code_lines / self.total_rules
        
    @property
    def border_width(self) -> float:
        bw = 1.5 + (self.code_ratio * 1.5)
        return min(bw, 8.0)
        
    @property
    def tree_width(self) -> int:
        """Width = 140 + (labels * 25) capped at 265px"""
        width = 140 + (self.total_labels * 25)
        return min(width, 265)
        
    @property
    def tree_height(self) -> int:
        """Height = 50 + (total_rules * 8) capped at 150px"""
        height = 50 + (self.total_rules * 8)
        return min(height, 150)

    @property
    def html_details(self) -> str:
        return f"Category: {self.label}<br>Total Labels: {self.total_labels}<br>Total Rules: {self.total_rules}<br>Code Ratio: {round(self.code_ratio, 2)}"

    def inject_parent_ids(self) -> None:
        """Hydrates the labels nodes with this macro category's ID"""
        for label in self.children:
            label.parent_id = self.id
            label.inject_parent_ids()

class ASTProjectInfo(BaseModel):
    """Metadata regarding the origin dataset file."""
    repoName: str
    agentsMdSource: str

class RootNode(BaseModel):
    """The root node encapsulating the entire parsed AST context."""
    id: str
    label: str
    type: Literal["root"] = "root"
    children: List[RuleCategory] = Field(default_factory=list)
    
    def hydrate_tree(self) -> None:
        for cat in self.children:
            cat.inject_parent_ids()


class AgentASTDocument(BaseModel):
    """The absolute root representation of an Extracted Agent Instruction Document."""
    projectInfo: ASTProjectInfo
    rootNode: RootNode
    thinking_process: Optional[str] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        self.rootNode.hydrate_tree()

    @property
    def repo_name(self) -> str:
        return self.projectInfo.repoName

    @property
    def source_file(self) -> str:
        return self.projectInfo.agentsMdSource
        
    @property
    def root_color(self) -> str:
        return ROOT_COLOR

    @property
    def force_graph_root_radius(self) -> int:
        return 25

    @property
    def tree_graph_root_radius(self) -> int:
        return 15
        
    @property
    def tree_width(self) -> int:
        return 220
        
    @property
    def tree_height(self) -> int:
        return 60
        
    @property
    def root_html_details(self) -> str:
        return f"Repository Name: {self.repo_name}"
