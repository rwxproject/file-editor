"""Markdown-specific file editing with structure awareness."""
import re
from pathlib import Path
from typing import Union, Optional, Iterator, NamedTuple
from ..core.stream_editor import StreamEditor
from ..core.safety import safe_edit_context
import logging

logger = logging.getLogger(__name__)


class MarkdownSection(NamedTuple):
    """Represents a markdown section."""
    level: int
    title: str
    start_line: int
    end_line: int
    content: str


class MarkdownEditor(StreamEditor):
    """Markdown file editor with structure awareness.
    
    This editor understands markdown structure and can efficiently edit
    specific sections without loading the entire document.
    """
    
    def __init__(self, file_path: Union[str, Path]):
        """Initialize markdown editor.
        
        Args:
            file_path: Path to the markdown file
        """
        super().__init__(file_path)
        self.heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
        self.sections: list[MarkdownSection] = []
        
    def _parse_structure(self) -> list[MarkdownSection]:
        """Parse markdown structure into sections."""
        sections = []
        current_section = None
        content_lines = []
        
        for line_num, line in enumerate(self.read_lines(), 1):
            line = line.rstrip('\n')
            heading_match = self.heading_pattern.match(line)
            
            if heading_match:
                # Save previous section if exists
                if current_section:
                    content = '\n'.join(content_lines)
                    section = MarkdownSection(
                        level=current_section['level'],
                        title=current_section['title'],
                        start_line=current_section['start_line'],
                        end_line=line_num - 1,
                        content=content
                    )
                    sections.append(section)
                
                # Start new section
                level = len(heading_match.group(1))
                title = heading_match.group(2)
                current_section = {
                    'level': level,
                    'title': title,
                    'start_line': line_num
                }
                content_lines = []
            else:
                if current_section:
                    content_lines.append(line)
                    
        # Handle last section
        if current_section:
            content = '\n'.join(content_lines)
            section = MarkdownSection(
                level=current_section['level'],
                title=current_section['title'],
                start_line=current_section['start_line'],
                end_line=line_num,
                content=content
            )
            sections.append(section)
            
        return sections
        
    def get_sections(self) -> list[MarkdownSection]:
        """Get all markdown sections."""
        if not self.sections:
            self.sections = self._parse_structure()
        return self.sections
        
    def find_section(self, title: str) -> Optional[MarkdownSection]:
        """Find section by title.
        
        Args:
            title: Section title to search for
            
        Returns:
            MarkdownSection if found, None otherwise
        """
        sections = self.get_sections()
        for section in sections:
            if section.title == title:
                return section
        return None
        
    def find_sections_by_level(self, level: int) -> list[MarkdownSection]:
        """Find all sections at a specific heading level.
        
        Args:
            level: Heading level (1-6)
            
        Returns:
            List of sections at the specified level
        """
        sections = self.get_sections()
        return [s for s in sections if s.level == level]
        
    def edit_section_streaming(self, target_title: str, new_content: str) -> bool:
        """Edit a markdown section using streaming approach.
        
        Args:
            target_title: Title of section to edit
            new_content: New content for the section
            
        Returns:
            True if section was found and edited
        """
        try:
            with safe_edit_context(self.file_path) as safe_op:
                temp_file = safe_op.get_temp_file()
                section_found = False
                
                with open(self.file_path, 'r') as infile, open(temp_file, 'w') as outfile:
                    in_target_section = False
                    current_level = 0
                    
                    for line in infile:
                        line_stripped = line.rstrip('\n')
                        heading_match = self.heading_pattern.match(line_stripped)
                        
                        if heading_match:
                            level = len(heading_match.group(1))
                            title = heading_match.group(2)
                            
                            if title == target_title:
                                # Found target section
                                in_target_section = True
                                current_level = level
                                section_found = True
                                
                                # Write heading and new content
                                outfile.write(line)
                                if new_content and not new_content.endswith('\n'):
                                    new_content += '\n'
                                outfile.write(new_content)
                                continue
                                
                            elif in_target_section and level <= current_level:
                                # End of target section
                                in_target_section = False
                                
                        # Write line if not in target section content
                        if not in_target_section:
                            outfile.write(line)
                            
                safe_op.atomic_replace(temp_file)
                return section_found
                
        except Exception as e:
            logger.error(f"Failed to edit markdown section: {e}")
            return False
            
    def insert_section(self, title: str, content: str, level: int = 2, 
                      after_section: Optional[str] = None) -> bool:
        """Insert a new section into the markdown document.
        
        Args:
            title: Title for new section
            content: Content for new section
            level: Heading level (1-6)
            after_section: Insert after this section (None for end)
            
        Returns:
            True if insertion was successful
        """
        try:
            with safe_edit_context(self.file_path) as safe_op:
                temp_file = safe_op.get_temp_file()
                
                heading = f"{'#' * level} {title}\n\n"
                if content and not content.endswith('\n'):
                    content += '\n'
                new_section = heading + content + '\n'
                
                if after_section is None:
                    # Append to end
                    with open(self.file_path, 'r') as infile, open(temp_file, 'w') as outfile:
                        outfile.write(infile.read())
                        outfile.write(new_section)
                else:
                    # Insert after specified section
                    with open(self.file_path, 'r') as infile, open(temp_file, 'w') as outfile:
                        in_target_section = False
                        target_level = 0
                        
                        for line in infile:
                            outfile.write(line)
                            
                            line_stripped = line.rstrip('\n')
                            heading_match = self.heading_pattern.match(line_stripped)
                            
                            if heading_match:
                                level_found = len(heading_match.group(1))
                                title_found = heading_match.group(2)
                                
                                if title_found == after_section:
                                    in_target_section = True
                                    target_level = level_found
                                elif in_target_section and level_found <= target_level:
                                    # End of target section - insert here
                                    outfile.write(new_section)
                                    in_target_section = False
                                    
                        # If we were still in target section at end, insert there
                        if in_target_section:
                            outfile.write(new_section)
                            
                safe_op.atomic_replace(temp_file)
                return True
                
        except Exception as e:
            logger.error(f"Failed to insert markdown section: {e}")
            return False
            
    def remove_section(self, title: str) -> bool:
        """Remove a section from the markdown document.
        
        Args:
            title: Title of section to remove
            
        Returns:
            True if section was found and removed
        """
        try:
            with safe_edit_context(self.file_path) as safe_op:
                temp_file = safe_op.get_temp_file()
                section_found = False
                
                with open(self.file_path, 'r') as infile, open(temp_file, 'w') as outfile:
                    in_target_section = False
                    current_level = 0
                    
                    for line in infile:
                        line_stripped = line.rstrip('\n')
                        heading_match = self.heading_pattern.match(line_stripped)
                        
                        if heading_match:
                            level = len(heading_match.group(1))
                            title_found = heading_match.group(2)
                            
                            if title_found == title:
                                # Found target section - start skipping
                                in_target_section = True
                                current_level = level
                                section_found = True
                                continue
                                
                            elif in_target_section and level <= current_level:
                                # End of target section
                                in_target_section = False
                                
                        # Write line if not in target section
                        if not in_target_section:
                            outfile.write(line)
                            
                safe_op.atomic_replace(temp_file)
                return section_found
                
        except Exception as e:
            logger.error(f"Failed to remove markdown section: {e}")
            return False
            
    def get_table_of_contents(self) -> str:
        """Generate a table of contents from the markdown structure.
        
        Returns:
            Markdown-formatted table of contents
        """
        sections = self.get_sections()
        toc_lines = []
        
        for section in sections:
            # Create proper indentation based on level
            indent = "  " * (section.level - 1)
            # Create markdown link
            link = section.title.lower().replace(' ', '-').replace('.', '')
            toc_line = f"{indent}- [{section.title}](#{link})"
            toc_lines.append(toc_line)
            
        return '\n'.join(toc_lines)
        
    def update_links(self, link_map: dict[str, str]) -> bool:
        """Update markdown links throughout the document.
        
        Args:
            link_map: Dictionary mapping old URLs to new URLs
            
        Returns:
            True if any links were updated
        """
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        updates_made = False
        
        def update_line(line: str) -> str:
            nonlocal updates_made
            
            def replace_link(match):
                nonlocal updates_made
                text = match.group(1)
                url = match.group(2)
                
                if url in link_map:
                    updates_made = True
                    return f"[{text}]({link_map[url]})"
                return match.group(0)
                
            return link_pattern.sub(replace_link, line)
            
        try:
            output_path = self.process_lines(update_line)
            if updates_made and output_path:
                with safe_edit_context(self.file_path) as safe_op:
                    safe_op.atomic_replace(output_path)
                return True
                
        except Exception as e:
            logger.error(f"Failed to update markdown links: {e}")
            
        return False