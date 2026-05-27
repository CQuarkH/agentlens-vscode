from typing import List, Literal, Optional, Dict
from pydantic import BaseModel, Field, root_validator
import math

# --- Visual Mappings ---
CATEGORY_COLORS: Dict[str, str] = {
    "General": "#E41A1C",
    "Implementation": "#984EA3",
    "Build": "#377EB8",
    "Management": "#FF7F00",
    "Quality": "#4DAF4A",
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
    line_start: Optional[int] = None
    line_end: Optional[int] = None

class AgentRule(BaseModel):
    """Leaf node representing an actionable rule/instruction."""
    id: str
    type: Literal["rule"] = "rule"
    content: RuleContent
    metadata: RuleMetadata
    
    # Optional parent reference injected during tree building for uniqueness mapping if needed
    parent_id: Optional[str] = None
    parent_color: Optional[str] = None

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
        if not self.parent_color:
            return SHOULD_COLOR
            
        import colorsys
        hex_code = self.parent_color.lstrip('#')
        r, g, b = tuple(int(hex_code[i:i+2], 16)/255.0 for i in (0, 2, 4))
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        
        # Fixed low semantic luminosity (Dark) for Rules to optimize white typography contrast
        r_new, g_new, b_new = colorsys.hls_to_rgb(h, 0.22, s)
        return '#%02x%02x%02x' % (int(r_new*255), int(g_new*255), int(b_new*255))
        
    @property
    def special_chars_count(self) -> int:
        import re
        symbols = re.findall(r'[\{\}\[\]\(\)<>/\\`#\*\+\-=\|@_]', self.content.text)
        return len(symbols)
        
    @property
    def tree_width(self) -> int:
        """Width based on absolute string character count"""
        chars = len(self.content.text)
        width = 120 + (chars * 2.5) 
        return int(max(120, min(400, width)))
        
    @property
    def tree_height(self) -> int:
        """Height encoded to density of programming syntax symbols"""
        height = 36 + (self.special_chars_count * 6)
        return int(min(height, 120))

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
        lines_info = f"<strong>Lines:</strong> {self.metadata.line_start} - {self.metadata.line_end}<br>" if self.metadata.line_start and self.metadata.line_end else ""
        return f"""
            {self.content.text}<br><br>
            <hr>
            <small>
            <strong>Original Header:</strong> {self.content.originalHeader}<br>
            <strong>Format:</strong> {self.metadata.format}<br>
            {lines_info}<strong>ID:</strong> {self.id}
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
    parent_color: Optional[str] = None
    area_ratio: float = 1.0

    @property
    def color(self) -> str:
        # Dynamic lightness interpolator based on the mathematical 2D Area of the node
        if not self.parent_color:
            return "#e2e8f0"
            
        import colorsys
        hex_code = self.parent_color.lstrip('#')
        r, g, b = tuple(int(hex_code[i:i+2], 16)/255.0 for i in (0, 2, 4))
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        
        # Larger areas inherit original base intensity. Smaller ones linearly wash out to #f2f2f2 (0.95 lightness).
        l_new = l + (1.0 - self.area_ratio) * (0.95 - l)
        
        r_new, g_new, b_new = colorsys.hls_to_rgb(h, l_new, s)
        return '#%02x%02x%02x' % (int(r_new*255), int(g_new*255), int(b_new*255)) 
        
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
        """Density formulation: 2.0px base + steeper multiplier, max 10px"""
        bw = 2.0 + (self.code_ratio * 4.0)
        return min(bw, 10.0)
        
    @property
    def computed_fre_score(self) -> float:
        if self.fre_score is not None:
            return self.fre_score
        if not self.children:
            return 100.0
            
        import textstat
        concatenated = " ".join([r.content.text for r in self.children])
        try:
            return max(0.0, textstat.flesch_reading_ease(concatenated))
        except:
            return 50.0

    @property
    def tree_width(self) -> int:
        """Width inverted to FRE: Harder readability (Low FRE) = Wider Block."""
        width = 180 - self.computed_fre_score
        return int(max(80, min(180, width)))
        
    @property
    def tree_height(self) -> int:
        """Height = 40 + (rules * 10) capped at 120px"""
        height = 40 + (self.total_rules * 10)
        return min(height, 120)

    @property
    def html_details(self) -> str:
        fre_val = round(self.computed_fre_score, 1)
        return f"Label: {self.label}<br>Total Rules: {self.count}<br>Code Ratio: {round(self.code_ratio, 2)}<br>FRE Cognitive Load: {fre_val}"

    def inject_parent_ids(self) -> None:
        for rule in self.children:
            rule.parent_id = self.id
            rule.parent_color = self.color

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
        bw = 2.0 + (self.code_ratio * 4.0)
        return min(bw, 10.0)
        
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
        """Hydrates the labels nodes with this macro category's ID and computes geometrical luminosity"""
        if not self.children:
            return
            
        areas = [(label.tree_width * label.tree_height) for label in self.children]
        max_area = max(areas)
        min_area = min(areas)
        
        for label in self.children:
            label.parent_id = self.id
            label.parent_color = self.color
            
            area = label.tree_width * label.tree_height
            
            if max_area == min_area:
                label.area_ratio = 1.0
            else:
                # Min-Max normalization spread to artificially bump visual contrast between similar labels
                normalized = (area - min_area) / (max_area - min_area)
                # The smallest label will get an area_ratio of 0.3 (very light), the largest gets 1.0 (pure color)
                label.area_ratio = 0.3 + (0.7 * normalized)
                
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
        return f"{self.projectInfo.repoName} - {self.source_file}"

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
