import sys
import os
import re
import unicodedata

# Kiwi 형태소 분석기 전역 변수
_kiwi = None

def get_kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        print("-> 형태소 분석기(Kiwi)를 로딩하는 중입니다...")
        _kiwi = Kiwi()
        
        # 1. 스크립트 파일과 동일한 디렉토리에서 user_words.txt 경로 탐색
        dict_filename = "user_words.txt"
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            script_dir = os.getcwd()
            
        dict_filepath = os.path.join(script_dir, dict_filename)
        
        # 2. 파일이 존재할 경우에만 사전에 등록
        if os.path.exists(dict_filepath):
            print(f"-> 사용자 사전 파일('{dict_filename}')을 읽어와 사전에 등록합니다...")
            try:
                registered_count = 0
                with open(dict_filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # 빈 줄이나 주석(#) 처리된 행은 건너뜀
                        if not line or line.startswith('#'):
                            continue
                        
                        parts = line.split()
                        word = parts[0]
                        pos = "NNP" # 기본값은 고유명사(Proper Noun)
                        
                        # 사용자가 품사(NNP/NNG)를 명시적으로 적어둔 경우 적용
                        if len(parts) > 1:
                            pos = parts[1].upper()
                            
                        _kiwi.add_user_word(word, pos)
                        registered_count += 1
                print(f"   성공: 사용자 사전에서 단어 {registered_count}개를 정상적으로 등록했습니다.")
            except Exception as e:
                print(f"   [경고] 사용자 사전 파일을 읽는 과정에서 오류가 발생했습니다: {e}")
        else:
            print(f"-> 알림: 사용자 사전 파일('{dict_filename}')을 찾을 수 없습니다. 기본 어휘로만 진행합니다.")
            print(f"   (추가하고 싶은 단어가 있다면 스크립트와 같은 위치에 '{dict_filename}' 파일을 생성하세요.)")
            
    return _kiwi

def load_file(filepath):
    """인코딩을 판별하여 파일을 읽어오고 유니코드를 정규화합니다."""
    try:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='cp949') as f:
                content = f.read()
    except Exception as e:
        print(f"   [오류] 파일을 읽을 수 없습니다: {e}")
        return None
    return unicodedata.normalize('NFC', content)

def save_file(filepath, content):
    """정리된 내용을 UTF-8 표준 인코딩으로 저장합니다."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"   [오류] 파일을 저장할 수 없습니다: {e}")
        return False

def clean_and_glue_text(text):
    """단락별로 줄바꿈을 지능적으로 결합합니다."""
    kiwi = get_kiwi()
    lines = text.splitlines()
    paragraphs = []
    current_para = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_para:
                paragraphs.append(current_para)
                current_para = []
            else:
                pass
        else:
            current_para.append(stripped)
    if current_para:
        paragraphs.append(current_para)
        
    cleaned_paragraphs = []
    for para in paragraphs:
        joined_text = kiwi.glue(para)
        cleaned_paragraphs.append(joined_text)
        
    return "\n\n".join(cleaned_paragraphs)

def verify_text(orig_text, clean_text):
    """공백을 제외한 두 텍스트의 글자가 완전히 일치하는지 검증합니다."""
    orig_stripped = re.sub(r'\s+', '', orig_text)
    clean_stripped = re.sub(r'\s+', '', clean_text)
    
    if orig_stripped == clean_stripped:
        return True, None
        
    # 불일치 발생 시 첫 불일치 지점 검색
    orig_len = len(orig_stripped)
    clean_len = len(clean_stripped)
    min_len = min(orig_len, clean_len)
    mismatch_idx = -1
    for i in range(min_len):
        if orig_stripped[i] != clean_stripped[i]:
            mismatch_idx = i
            break
    if mismatch_idx == -1:
        mismatch_idx = min_len
        
    return False, (mismatch_idx, orig_stripped, clean_stripped)

def main():
    if len(sys.argv) < 2:
        print("사용법: python batch_processor.py <대상_폴더_경로>")
        print("예시: python batch_processor.py ./소설폴더")
        sys.exit(1)
        
    target_dir = sys.argv[1]
    
    if not os.path.isdir(target_dir):
        print(f"오류: '{target_dir}'은(는) 유효한 폴더 경로가 아닙니다.")
        sys.exit(1)
        
    print(f"==================================================")
    print(f" 탐색 시작 폴더: {os.path.abspath(target_dir)}")
    print(f"==================================================")
    
    orig_files = []
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.endswith('.txt') and not file.endswith('_정리.txt'):
                orig_files.append(os.path.join(root, file))
                
    total_count = len(orig_files)
    print(f"-> 대상 파일 {total_count}개를 찾았습니다.\n")
    
    if total_count == 0:
        print("처리할 파일이 없습니다.")
        return

    skipped_count = 0
    created_count = 0
    failed_verifications = []

    for idx, orig_path in enumerate(orig_files, 1):
        file_base, file_ext = os.path.splitext(orig_path)
        clean_path = f"{file_base}_정리{file_ext}"
        
        relative_orig_path = os.path.relpath(orig_path, target_dir)
        print(f"[{idx}/{total_count}] {relative_orig_path}")
        
        orig_content = load_file(orig_path)
        if orig_content is None:
            continue
            
        is_already_exists = os.path.exists(clean_path)
        clean_content = None
        
        if is_already_exists:
            print("   -> 정리 파일이 이미 존재합니다. 생성을 생략하고 검증만 진행합니다.")
            clean_content = load_file(clean_path)
            skipped_count += 1
        else:
            print("   -> 정리 파일을 새로 생성하는 중입니다...")
            clean_content = clean_and_glue_text(orig_content)
            if save_file(clean_path, clean_content):
                created_count += 1
            else:
                continue
                
        if clean_content is not None:
            is_valid, details = verify_text(orig_content, clean_content)
            if is_valid:
                print("   -> [검증 결과] 합격 (글자 유실 없음)")
            else:
                print("   -> [검증 결과] 불합격! (일부 글자 불일치 발견)")
                failed_verifications.append((relative_orig_path, details))
        print()

    print(f"==================================================")
    print(f"                    최종 리포트")
    print(f"==================================================")
    print(f" 전체 대상 파일 수 : {total_count}개")
    print(f" 신규 생성된 파일  : {created_count}개")
    print(f" 이미 존재하여 생략: {skipped_count}개")
    print(f" 검증 실패 파일 수 : {len(failed_verifications)}개")
    print(f"==================================================")
    
    if failed_verifications:
        print("\n⚠️ 검증이 실패한 파일 목록 (글자 유실/변형 의심):")
        for filepath, details in failed_verifications:
            mismatch_idx, orig_stripped, clean_stripped = details
            print(f"- 파일명: {filepath}")
            print(f"  위치: 약 {mismatch_idx + 1:,}번째 글자 부근")
            
            start = max(0, mismatch_idx - 15)
            end_orig = min(len(orig_stripped), mismatch_idx + 15)
            end_clean = min(len(clean_stripped), mismatch_idx + 15)
            
            marker = " " * (mismatch_idx - start) + "▲"
            print(f"  원본: ... {orig_stripped[start:end_orig]} ...")
            print(f"  정리: ... {clean_stripped[start:end_clean]} ...")
            print(f"        {marker}")
            print()
    else:
        print("\n✨ 모든 파일의 알맹이 글자가 완벽히 보존되었습니다! 이상 무.")

if __name__ == "__main__":
    main()
