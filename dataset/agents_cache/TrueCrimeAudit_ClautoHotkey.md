# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ClautoHotkey is a comprehensive AutoHotkey v2 (AHK v2) development environment with structured prompts, modules, and scripts for AI-assisted AutoHotkey development. This repository contains hundreds of scripts demonstrating AHK v2 features including GUI applications, automation tools, and system utilities.

## Core Architecture

**Language**: AutoHotkey v2 only (no v1 support)
**Primary Focus**: Object-oriented GUI applications and system automation
**Structure**: Modular design with extensive library support and structured instruction system

## Common Commands

### Running AutoHotkey Scripts
```bash
# Preferred execution method with UTF-8 error output
& "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe" /ErrorStdOut=utf-8 "<script_path>"

# Quick test targets
& "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe" /ErrorStdOut=utf-8 "Tests\Test_Basic.ahk"
& "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe" /ErrorStdOut=utf-8 "Tests\Other_TestingSystem.ahk"
```

### User-facing Tools
- `_UltiLog.ahk` - Ultimate Logger for AI interaction logs and testing
- `_Lists.ahk` - JSON List Editor with dark theme
- `Scripts\Clip_SearchCode.ahk` - Code search and replacement tool
- `Scripts\ClipboardHistoryCombiner.ahk` - Clipboard history management
- `_Context_Creator.ahk` - Module combination tool for LLM context

## High-Level Architecture

### Module System
The project uses a sophisticated structured instruction system organized in `/Modules/`:

**PRIMARY MODULE**:
- `Module_Instructions.md` - **ALWAYS START HERE** - Contains the foundational AHK v2 instruction framework, cognitive tier system, and structured development methodology

**KEYWORD-TRIGGERED MODULES** (reference only when specific keywords appear in requests):
- `Module_Classes.md` - OOP patterns, constructors, inheritance
- `Module_GUI.md` - GUI construction, events, layout mathematics  
- `Module_DataStructures.md` - Collections, Map() usage, data handling
- `Module_Objects.md` - Object manipulation, property patterns
- `Module_Arrays.md` - Array operations, iteration, transformations
- `Module_TextProcessing.md` - String operations, regex, formatting
- `Module_DynamicProperties.md` - Property descriptors, getters/setters
- `Module_Escapes.md` - Escaping rules for quotes, regex, paths
- `Module_ClassPrototyping.md` - Prototyping class structures

**INSTRUCTION METHODOLOGY**: Claude Code follows the structured approach defined in Module_Instructions.md, using keyword triggers to selectively reference additional modules as needed for specific implementation requirements.

### Cursor/IDE Integration
- **Rules**: Modern project rules in `.cursor/rules/` as MDC files
- **Core Rules**: 
  - `00-always-linter.mdc` - Always-on linter enforcement
  - `10-core-ahk-system.mdc` - Core AHK v2 system constraints
  - Additional rules for objects, GUI layout, text processing
- **Legacy**: `.cursorrules.md` references modern rule locations

### Directory Structure

```
/Modules/           - Core instruction modules for AI agents
/AHK_Notes/         - Extensive documentation and examples
  /Classes/         - Class-specific examples and patterns
  /Concepts/        - Advanced programming concepts
  /Methods/         - Method implementations and techniques
  /Patterns/        - Design patterns in AHK v2
  /Snippets/        - Code snippets and examples
/Scripts/           - User-facing utility applications
/Tests/             - Test scripts and validation tools
/Lib/               - Shared libraries and utility functions
```

## AHK v2 Coding Standards

This project enforces strict AutoHotkey v2 coding standards:

### Core Requirements
- **Pure AHK v2 OOP**: Instantiate classes without `new` keyword
- **Data Storage**: Use `Map()` for all key-value storage (no object literals)
- **Event Binding**: All callbacks must use `.Bind(this)`
- **Resource Cleanup**: Implement `__Delete()` methods for proper cleanup
- **Variable Scoping**: Explicit variable declarations required
- **Fat Arrow Functions**: Single-line expressions only (no `{}` blocks)

### GUI Standards
- Class-based GUI construction only
- Deterministic layout with mathematical positioning
- Proper event handling with `OnEvent()`
- Input validation and error reporting
- Clean close/escape behaviors

### Data Handling
- Arrays are 1-based in AHK v2
- PCRE regex flags: `i/m/s/x` only
- Backtick escaping for quotes and special characters
- Strict comma/colon syntax adherence

## Development Workflow

### For AutoHotkey Development - Structured Instruction System

**PRIMARY REFERENCE**: Always start with `Module_Instructions.md` for foundational AHK v2 coding standards and structured approach.

**KEYWORD-TRIGGERED MODULE REFERENCES**: After consulting Module_Instructions.md, reference additional modules only when specific keywords appear in requests:

- **"class"** → `Module_Classes.md` - OOP patterns, constructors, inheritance
- **"gui"** → `Module_GUI.md` - GUI construction, events, layout mathematics  
- **"map", "object", "storage"** → `Module_Objects.md` - Object manipulation, property patterns
- **"array", "list", "collection"** → `Module_Arrays.md` - Array operations, iteration, transformations
- **"string", "regex"** → `Module_TextProcessing.md` - String operations, regex, formatting
- **"data", "examples"** → `Module_DataStructures.md` - Collections, Map() usage, data handling
- **"backtick", "escape", "quote"** → `Module_Escapes.md` - Escaping rules for quotes, regex, paths
- **"property", "getter", "setter"** → `Module_DynamicProperties.md` - Property descriptors, getters/setters
- **"prototype", "structure"** → `Module_ClassPrototyping.md` - Prototyping class structures

**STRUCTURED APPROACH**: 
1. Parse and understand the user's request using Module_Instructions.md framework
2. Identify relevant AHK v2 concepts and complexity markers
3. Reference appropriate modules based on keyword triggers above
4. Apply cognitive tier system (think/think harder/ultrathink) as needed
5. Design solution using pure AHK v2 OOP principles
6. Implement with proper validation and edge case consideration
7. Test with scripts in `/Tests/` directory
8. Validate syntax with AHK v2 interpreter

### Key Design Principles
- **No Comments**: Code should be self-documenting through clear naming
- **Error Handling**: Never use empty catch blocks; implement specific error strategies  
- **Performance**: Consider object lifetime and garbage collection
- **Maintainability**: Design for easy modification and extension
- **User Safety**: Validate all inputs and provide meaningful error messages

## Important Notes

- **AHK v2 Only**: No AutoHotkey v1 code or compatibility
- **No Node.js/MCP**: This is a pure AHK environment; do not search for or start web services
- **Targeted Reading**: Avoid broad discovery scans; read files relevant to specific requests
- **Module-First**: Always start with Module_Instructions.md, then reference additional modules based on keyword triggers
- **Structured Approach**: Follow the cognitive tier system and structured instruction methodology
- **Clean Architecture**: Follow established patterns and maintain consistency with existing code

This repository represents a mature AutoHotkey v2 development environment optimized for AI-assisted development with comprehensive documentation and strict quality standards.

