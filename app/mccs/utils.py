"""
This module provides utility functions for the MCCS package.

Currently, it includes a function to parse MCCS VCP capability strings.
"""
import re
from typing import List, Dict, Optional, Union # For type hinting

def parse_mccs_vcp_capabilities(vcp_string: str) -> List[Dict[str, Union[str, Optional[List[str]]]]]:
    """
    Parses the "vcp" section of an MCCS capabilities string.

    The VCP section contains a list of supported VCP codes. Continuous VCPs
    are represented by their hexadecimal code. Non-continuous VCPs are
    represented by their hexadecimal code followed by a list of supported
    hexadecimal values in parentheses, separated by spaces.

    Example from the prompt: "10 14(01 05 08)"
    - 0x10 is a continuous VCP.
    - 0x14 is a non-continuous VCP with supported values 0x01, 0x05, 0x08.

    Args:
        vcp_string (str): The VCP capabilities string.
                          e.g., "10 14(01 05 08) 60(AA BB CC) D6 E0()"

    Returns:
        List[Dict[str, Union[str, Optional[List[str]]]]]:
            A list of dictionaries, where each dictionary represents a
            parsed VCP feature. Each dictionary has the following keys:
            - 'code' (str): The hexadecimal VCP code (e.g., "10").
            - 'type' (str): Either "continuous" or "non-continuous".
            - 'values' (Optional[List[str]]):
                - For "non-continuous" VCPs, this is a list of
                  hexadecimal string values (e.g., ["01", "05", "08"]).
                  The list will be empty if the parentheses are empty (e.g., "E0()").
                - For "continuous" VCPs, this will be None.
    """
    parsed_vcps: List[Dict[str, Union[str, Optional[List[str]]]]] = []

    # Regex to find individual VCP entries.
    # An entry is a hex code, optionally followed by parentheses containing values.
    # - Group 1: ([0-9A-Fa-f]+) captures the hexadecimal VCP code.
    # - Group 2: (.*?) captures the content within parentheses if parentheses are present.
    #   - This group (match.group(2)) will be None if parentheses are not present.
    #   - It will be an empty string if parentheses are present but empty (e.g., "E0()").
    #   - It will contain the space-separated values if present (e.g., "01 05 08").
    vcp_pattern = re.compile(r"([0-9A-Fa-f]+)(?:\((.*?)\))?")

    for match in vcp_pattern.finditer(vcp_string):
        code: str = match.group(1)
        # values_content_capture is the string inside the parentheses, or None if no parentheses
        values_content_capture: Optional[str] = match.group(2)

        vcp_info: Dict[str, Union[str, Optional[List[str]]]] = {'code': code}

        if values_content_capture is not None:  # Parentheses were present, so it's non-continuous
            vcp_info['type'] = 'non-continuous'
            # Strip leading/trailing whitespace from the content inside parentheses
            # and then split by whitespace to get individual values.
            # If content was empty or only whitespace (e.g., "()" or "(   )"),
            # values list will be empty.
            stripped_values_content = values_content_capture.strip()
            if stripped_values_content:
                vcp_info['values'] = stripped_values_content.split()
            else:
                vcp_info['values'] = []
        else:  # No parentheses, so it's a continuous VCP
            vcp_info['type'] = 'continuous'
            vcp_info['values'] = None
        
        parsed_vcps.append(vcp_info)

    return parsed_vcps

if __name__ == '__main__':
    # Example usage based on the prompt
    example_string_1 = "10 14(01 05 08)"
    parsed_data_1 = parse_mccs_vcp_capabilities(example_string_1)
    print(f"Parsing '{example_string_1}':")
    for item in parsed_data_1:
        print(item)
    # Expected output for example_string_1:
    # Parsing '10 14(01 05 08)':
    # {'code': '10', 'type': 'continuous', 'values': None}
    # {'code': '14', 'type': 'non-continuous', 'values': ['01', '05', '08']}

    print("-" * 30)

    # A more complex example
    example_string_2 = "02 D6(00 01 02 04) BF E0() AC(0A F3 1C)"
    parsed_data_2 = parse_mccs_vcp_capabilities(example_string_2)
    print(f"Parsing '{example_string_2}':")
    for item in parsed_data_2:
        print(item)
    # Expected output for example_string_2:
    # Parsing '02 D6(00 01 02 04) BF E0() AC(0A F3 1C)':
    # {'code': '02', 'type': 'continuous', 'values': None}
    # {'code': 'D6', 'type': 'non-continuous', 'values': ['00', '01', '02', '04']}
    # {'code': 'BF', 'type': 'continuous', 'values': None}
    # {'code': 'E0', 'type': 'non-continuous', 'values': []}
    # {'code': 'AC', 'type': 'non-continuous', 'values': ['0A', 'F3', '1C']}

    print("-" * 30)

    # Example with extra spaces inside parentheses
    example_string_3 = "F0( 01  02   03 ) F1"
    parsed_data_3 = parse_mccs_vcp_capabilities(example_string_3)
    print(f"Parsing '{example_string_3}':")
    for item in parsed_data_3:
        print(item)
    # Expected output for example_string_3:
    # Parsing 'F0( 01  02   03 ) F1':
    # {'code': 'F0', 'type': 'non-continuous', 'values': ['01', '02', '03']}
    # {'code': 'F1', 'type': 'continuous', 'values': None}

    print("-" * 30)
    
    # Example with empty input string
    example_string_4 = ""
    parsed_data_4 = parse_mccs_vcp_capabilities(example_string_4)
    print(f"Parsing '{example_string_4}':")
    print(parsed_data_4)
    # Expected output for example_string_4:
    # Parsing '':
    # []

    print("-" * 30)

    # Example with only spaces or malformed (non-hex code)
    example_string_5 = "   XX(01) FF  "
    parsed_data_5 = parse_mccs_vcp_capabilities(example_string_5)
    print(f"Parsing '{example_string_5}':")
    for item in parsed_data_5:
        print(item)
    # Expected output for example_string_5 (XX is not a valid hex code for the VCP itself):
    # Parsing '   XX(01) FF  ':
    # {'code': 'FF', 'type': 'continuous', 'values': None}