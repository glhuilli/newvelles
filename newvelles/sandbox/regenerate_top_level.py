import json
from collections import defaultdict
from typing import Dict, List

import click

from newvelles.utils.text import get_top_words_spacy


class GroupingAnalyzer:
    def __init__(self, json_path: str):
        with open(json_path, "r") as f:
            self.data = json.load(f)

    def get_group_structure(self) -> Dict[str, Dict[str, List[str]]]:
        """Returns a simplified structure of the groups for analysis"""
        structure: Dict[str, Dict[str, List[str]]] = defaultdict(dict)
        for top_level, lower_groups in self.data.items():
            for lower_level, titles in lower_groups.items():
                structure[top_level][lower_level] = list(titles.keys())
        return structure

    def analyze_top_level_group(self, top_level_group: str) -> Dict:
        """Analyzes a specific top-level group"""
        all_titles = []
        lower_groups_text = []

        for lower_group, titles in self.data[top_level_group].items():
            titles_list = list(titles.keys())
            all_titles.extend(titles_list)
            # Combine all titles in lower group for analysis
            lower_groups_text.append(
                {
                    "group": lower_group,
                    "combined_text": " ".join(titles_list),
                    "titles": titles_list,
                }
            )

        return {
            "total_titles": len(all_titles),
            "titles": all_titles,
            "lower_groups": len(lower_groups_text),
            "spacy_keywords": get_top_words_spacy(all_titles, top_n=10),
            "lower_group_keywords": {
                group["group"]: get_top_words_spacy(group["titles"], top_n=5)
                for group in lower_groups_text
            },
        }

    def suggest_new_top_level_name(self, top_level_group: str, num_keywords: int = 5) -> List[str]:
        """Suggests alternative names for top-level group based on different strategies"""
        analysis = self.analyze_top_level_group(top_level_group)

        suggestions = []

        # Strategy 1: Most frequent keywords across all titles
        top_keywords = [word for word, _ in analysis["spacy_keywords"][:num_keywords]]
        suggestions.append(f"Keywords based: {' '.join(top_keywords)}")

        # Strategy 2: Common themes from lower groups
        common_lower_keywords = set()
        for group_keywords in analysis["lower_group_keywords"].values():
            common_lower_keywords.update([word for word, _ in group_keywords])
        suggestions.append(f"Common themes: {' '.join(list(common_lower_keywords)[:num_keywords])}")

        # Combined strategy: top keywords from all lower groups
        combined_suggestions = list(set(top_keywords + list(common_lower_keywords)[:num_keywords]))

        suggestions.append(f"Combined: {' '.join(combined_suggestions)}")
        return suggestions


def analyze_grouping_file(json_path: str):
    """Main function to analyze a grouping file"""
    analyzer = GroupingAnalyzer(json_path)

    print("=== Grouping Analysis ===")
    print(f"Total top-level groups: {len(analyzer.data)}")

    for top_group in analyzer.data.keys():
        print(f"\nAnalyzing group: {top_group}")
        analysis = analyzer.analyze_top_level_group(top_group)
        print(f"Total titles: {analysis['total_titles']}")
        print(f"Titles: {analysis['titles']}")
        print(f"Lower groups: {analysis['lower_groups']}")
        print("\nSuggested alternative names:")
        for suggestion in analyzer.suggest_new_top_level_name(top_group, num_keywords=5):
            print(f"- {suggestion}")


@click.command()
@click.option(
    "--json_visualization_file",
    default="./data/visualization_example.json",
    help="JSON file with visualization data output",
)
def main(json_visualization_file):
    analyze_grouping_file(json_visualization_file)


if __name__ == "__main__":
    main()
