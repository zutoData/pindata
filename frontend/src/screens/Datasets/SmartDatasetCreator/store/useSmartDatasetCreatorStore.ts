import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { SmartDatasetCreatorState, SmartDatasetCreatorActions, SelectedFile, DatasetCollection } from '../types';
import { DATASET_TYPES, FORMAT_DETAILS } from '../constants';
import { FileService } from '../../../../services/file.service';
import { LLMService } from '../../../../services/llm.service';
import { LLMConfig } from '../../../../types/llm';
import { useTranslation } from 'react-i18next';

// 初始状态
const initialState: SmartDatasetCreatorState = {
  // 步骤状态
  currentStep: 1,
  
  // 数据状态
  selectedFiles: [],
  availableFiles: [],
  datasetCollections: [],
  datasetType: 'qa-pairs',
  outputFormat: 'Alpaca',
  datasetName: '',
  datasetDescription: '',
  processingConfig: {
    model: '',
    temperature: 0.7,
    maxTokens: 2000,
    batchSize: 10,
    customPrompt: '',
    chunkSize: 1000,
    chunkOverlap: 200,
    preserveStructure: true,
    splitByHeaders: true,
    maxDocumentLength: 50000, // 预训练数据清洗最大文档长度：5万字符
    // 思考过程配置默认值
    enableThinkingProcess: false,
    reasoningExtractionMethod: null,
    reasoningExtractionConfig: null,
    distillationPrompt: '请详细说明你的思考过程，包括分析步骤和推理逻辑：',
    includeThinkingInOutput: false
  },
  availableLLMConfigs: [],
  
  // 任务状态
  taskInfo: null,
  
  // UI状态
  isLoading: false,
  loadingFiles: false,
  loadingCollections: false,
  loadingLLMConfigs: false,
  progress: 0,
  error: null,
  showFormatDetails: false,
  selectedFormat: null,
};

// 模拟API调用获取文件列表
const mockLoadAvailableFiles = async (): Promise<SelectedFile[]> => {
  await new Promise(resolve => setTimeout(resolve, 1000));
  return [
    { id: '1', name: '产品介绍.md', path: '/rawdata/docs/产品介绍.md', size: 1024, type: 'markdown', selected: false },
    { id: '2', name: '用户手册.md', path: '/rawdata/docs/用户手册.md', size: 2048, type: 'markdown', selected: false },
    { id: '3', name: 'FAQ.md', path: '/rawdata/docs/FAQ.md', size: 1536, type: 'markdown', selected: false },
    { id: '4', name: '技术文档.md', path: '/rawdata/technical/技术文档.md', size: 4096, type: 'markdown', selected: false },
    { id: '5', name: '更新日志.md', path: '/rawdata/changelog/更新日志.md', size: 512, type: 'markdown', selected: false }
  ];
};

// 模拟生成过程
const mockGenerateDataset = async (onProgress: (progress: number) => void): Promise<void> => {
  for (let i = 0; i <= 100; i += 10) {
    await new Promise(resolve => setTimeout(resolve, 500));
    onProgress(i);
  }
};

export const useSmartDatasetCreatorStore = create<SmartDatasetCreatorState & SmartDatasetCreatorActions>()(
  devtools(
    (set, get) => ({
      ...initialState,

      // 步骤控制
      nextStep: () => {
        const { currentStep } = get();
        const totalSteps = 5;
        if (currentStep < totalSteps) {
          set({ currentStep: currentStep + 1 });
        }
      },

      prevStep: () => {
        const { currentStep } = get();
        if (currentStep > 1) {
          set({ currentStep: currentStep - 1 });
        }
      },

      setCurrentStep: (step: number) => {
        set({ currentStep: step });
      },

      // 文件管理
      setAvailableFiles: (files: SelectedFile[]) => {
        set({ availableFiles: files });
      },

      handleFileSelection: (fileId: string, selected: boolean) => {
        const { availableFiles, selectedFiles } = get();
        
        // 更新可用文件列表
        const updatedAvailableFiles = availableFiles.map(file => 
          file.id === fileId ? { ...file, selected } : file
        );
        
        // 更新已选择文件列表
        let updatedSelectedFiles: SelectedFile[];
        if (selected) {
          const file = availableFiles.find(f => f.id === fileId);
          if (file) {
            updatedSelectedFiles = [...selectedFiles, { ...file, selected: true }];
          } else {
            updatedSelectedFiles = selectedFiles;
          }
        } else {
          updatedSelectedFiles = selectedFiles.filter(f => f.id !== fileId);
        }

        set({ 
          availableFiles: updatedAvailableFiles,
          selectedFiles: updatedSelectedFiles 
        });
      },

      handleSelectAll: (selected: boolean) => {
        const { availableFiles } = get();
        
        const updatedAvailableFiles = availableFiles.map(file => ({ ...file, selected }));
        const updatedSelectedFiles = selected ? 
          availableFiles.map(f => ({ ...f, selected: true })) : 
          [];

        set({ 
          availableFiles: updatedAvailableFiles,
          selectedFiles: updatedSelectedFiles 
        });
      },

      loadAvailableFiles: async () => {
        set({ loadingFiles: true, error: null });
        try {
          const files = await mockLoadAvailableFiles();
          set({ availableFiles: files });
        } catch (error) {
          set({ error: '加载文件列表失败' });
        } finally {
          set({ loadingFiles: false });
        }
      },

      // 数据集合管理 - 新增方法
      loadDatasetCollections: async () => {
        set({ loadingCollections: true, error: null });
        try {
          const libraries = await FileService.getLibraries();
          const collections: DatasetCollection[] = [];
          
          // 为每个数据集合获取MD文件
          for (const library of libraries) {
            try {
              const markdownFiles = await FileService.getLibraryMarkdownFiles(library.id);
              collections.push({
                library,
                markdownFiles,
                expanded: false,
                selected: false
              });
            } catch (error) {
              console.error(`获取数据集合 ${library.name} 的MD文件失败:`, error);
              collections.push({
                library,
                markdownFiles: [],
                expanded: false,
                selected: false
              });
            }
          }
          
          set({ datasetCollections: collections });
        } catch (error) {
          set({ error: '加载数据集合失败' });
        } finally {
          set({ loadingCollections: false });
        }
      },

      toggleCollectionExpanded: (libraryId: string) => {
        const { datasetCollections } = get();
        const updatedCollections = datasetCollections.map(collection =>
          collection.library.id === libraryId
            ? { ...collection, expanded: !collection.expanded }
            : collection
        );
        set({ datasetCollections: updatedCollections });
      },

      handleCollectionSelection: (libraryId: string, selected: boolean) => {
        const { datasetCollections, selectedFiles } = get();
        const collection = datasetCollections.find(c => c.library.id === libraryId);
        if (!collection) return;

        // 更新集合选中状态
        const updatedCollections = datasetCollections.map(c =>
          c.library.id === libraryId ? { ...c, selected } : c
        );

        // 更新选中的文件列表
        let updatedSelectedFiles = [...selectedFiles];
        
        if (selected) {
          // 选中整个集合：添加所有MD文件到选中列表
          const newFiles: SelectedFile[] = collection.markdownFiles.map(file => ({
            id: file.id,
            name: file.original_filename || file.filename,
            path: file.minio_object_name,
            size: file.file_size,
            type: 'markdown',
            selected: true,
            libraryId: libraryId,
            libraryName: collection.library.name,
            isMarkdown: true,
            originalFile: file
          }));
          
          // 移除同一library的现有文件，然后添加新文件
          updatedSelectedFiles = updatedSelectedFiles.filter(f => f.libraryId !== libraryId);
          updatedSelectedFiles.push(...newFiles);
        } else {
          // 取消选中整个集合：移除该集合的所有文件
          updatedSelectedFiles = updatedSelectedFiles.filter(f => f.libraryId !== libraryId);
        }

        set({ 
          datasetCollections: updatedCollections,
          selectedFiles: updatedSelectedFiles
        });
      },

      handleCollectionFileSelection: (libraryId: string, fileId: string, selected: boolean) => {
        const { datasetCollections, selectedFiles } = get();
        const collection = datasetCollections.find(c => c.library.id === libraryId);
        if (!collection) return;

        const file = collection.markdownFiles.find(f => f.id === fileId);
        if (!file) return;

        let updatedSelectedFiles = [...selectedFiles];
        
        if (selected) {
          // 检查是否已存在
          if (!updatedSelectedFiles.find(f => f.id === fileId)) {
            const newFile: SelectedFile = {
              id: file.id,
              name: file.original_filename || file.filename,
              path: file.minio_object_name,
              size: file.file_size,
              type: 'markdown',
              selected: true,
              libraryId: libraryId,
              libraryName: collection.library.name,
              isMarkdown: true,
              originalFile: file
            };
            updatedSelectedFiles.push(newFile);
          }
        } else {
          updatedSelectedFiles = updatedSelectedFiles.filter(f => f.id !== fileId);
        }

        // 检查是否整个集合都被选中了
        const selectedFileIds = updatedSelectedFiles.filter(f => f.libraryId === libraryId).map(f => f.id);
        const allSelected = collection.markdownFiles.length > 0 && 
                          collection.markdownFiles.every(f => selectedFileIds.includes(f.id));

        // 更新集合状态
        const updatedCollections = datasetCollections.map(c =>
          c.library.id === libraryId ? { ...c, selected: allSelected } : c
        );

        set({ 
          datasetCollections: updatedCollections,
          selectedFiles: updatedSelectedFiles
        });
      },

      // 数据集配置
      setDatasetType: (type: string) => {
        const datasetType = DATASET_TYPES.find(t => t.id === type);
        const outputFormat = datasetType && datasetType.formats.length > 0 ? 
          datasetType.formats[0] : 'Alpaca';
        
        set({ 
          datasetType: type,
          outputFormat 
        });
      },

      setOutputFormat: (format: string) => {
        set({ outputFormat: format });
      },

      setDatasetName: (name: string) => {
        set({ datasetName: name });
      },

      setDatasetDescription: (description: string) => {
        set({ datasetDescription: description });
      },

      // 模型配置
      setProcessingConfig: (config) => {
        set(state => ({ 
          processingConfig: { ...state.processingConfig, ...config }
        }));
      },

      loadLLMConfigs: async () => {
        set({ loadingLLMConfigs: true, error: null });
        try {
          const { configs } = await LLMService.getConfigs({ is_active: true });
          set({ 
            availableLLMConfigs: configs,
            // 如果还没有选择模型且有可用配置，选择默认配置或第一个
            processingConfig: get().processingConfig.model === '' && configs.length > 0 ? {
              ...get().processingConfig,
              model: configs.find(c => c.is_default)?.id || configs[0].id
            } : get().processingConfig
          });
        } catch (error) {
          set({ error: '加载模型配置失败' });
        } finally {
          set({ loadingLLMConfigs: false });
        }
      },

      generatePrompt: () => {
        const { 
          datasetType, 
          outputFormat, 
          selectedFiles, 
          datasetName, 
          datasetDescription,
          processingConfig 
        } = get();
        
        // Get current language from i18next
        const currentLanguage = localStorage.getItem('i18nextLng') || 'zh';
        const isEnglish = currentLanguage === 'en';
        const isJapanese = currentLanguage === 'ja';
        
        const currentDatasetType = DATASET_TYPES.find(t => t.id === datasetType);
        const formatDetails = FORMAT_DETAILS[outputFormat as keyof typeof FORMAT_DETAILS];
        
        if (!currentDatasetType) return '';
        
        // 对于预训练数据清洗，直接返回优化的提示词
        if (datasetType === 'pretraining-data-cleaning') {
          if (isEnglish) {
            return `You are a professional pretraining data cleaning assistant. Your task is to clean raw text into high-quality corpus suitable for large language model pretraining.

Please clean the text according to the following requirements:

1. **Content Cleaning**:
   - Remove markdown tags, HTML tags, extra blank lines and spaces
   - Remove meaningless repetitive content and noise text
   - Retain valuable information and complete sentences
   - Ensure natural and fluent language

2. **Format Requirements**:
   - Each cleaned corpus paragraph must be wrapped in the following format: [语料开始]...[语料结束]
   - If there are multiple independent corpus paragraphs, each should be wrapped separately
   - Corpus content should ensure complete sentences and clear paragraph logic

3. **Quality Standards**:
   - Corpus length should be at least 30 characters
   - Content should have practical value, avoid pure titles or directories
   - Maintain the original language style and professionalism

Please strictly follow the above requirements and wrap each cleaned corpus with [语料开始] and [语料结束] tags.`;
          } else if (isJapanese) {
            return `あなたは専門的な事前学習データクリーニングアシスタントです。あなたのタスクは、生のテキストを大規模言語モデルの事前学習に適した高品質なコーパスにクリーニングすることです。

以下の要件に従ってテキストをクリーニングしてください：

1. **コンテンツクリーニング**：
   - マークダウンタグ、HTMLタグ、余分な空行とスペースを除去
   - 無意味な反復コンテンツとノイズテキストを除去
   - 価値のある情報と完全な文を保持
   - 自然で流暢な言語を確保

2. **フォーマット要件**：
   - クリーニングされた各コーパス段落は以下の形式で包む必要があります：[语料开始]...[语料结束]
   - 複数の独立したコーパス段落がある場合、それぞれを個別に包んでください
   - コーパス内容は完全な文と明確な段落論理を保証してください

3. **品質基準**：
   - コーパス長は最低30文字
   - 内容は実用的価値を持ち、純粋なタイトルや目次を避ける
   - 元の言語スタイルと専門性を維持

上記の要件に厳密に従い、クリーニングされた各コーパスを[语料开始]と[语料结束]タグで包んでください。`;
          } else {
            return `你是一个专业的预训练数据清洗助理。你的任务是将原始文本清洗成适合大语言模型预训练的高质量语料。

请按照以下要求清洗文本：

1. **内容清洗**：
   - 去除markdown标记、HTML标签、多余的空行和空格
   - 去除无意义的重复内容和噪声文本
   - 保留有价值的信息和完整的句子
   - 确保语言自然流畅

2. **格式要求**：
   - 每个清洗后的语料段落必须用以下格式包裹：[语料开始]...[语料结束]
   - 如果有多个独立的语料段落，每个都要单独包裹
   - 语料内容要保证句子完整，段落逻辑清晰

3. **质量标准**：
   - 语料长度至少30个字符
   - 内容要有实际价值，避免纯标题或目录
   - 保持原文的语言风格和专业性

请严格按照上述要求处理，并将每个清洗后的语料用[语料开始]和[语料结束]标记包裹。`;
          }
        }
        
        // 构建个性化的项目背景
        let projectContext = '';
        if (datasetName || datasetDescription) {
          if (isEnglish) {
            projectContext = `\n## Project Background`;
            if (datasetName) {
              projectContext += `\nDataset Name: ${datasetName}`;
            }
            if (datasetDescription) {
              projectContext += `\nProject Description: ${datasetDescription}`;
            }
            projectContext += `\nPlease ensure the generated data is consistent with project objectives.`;
          } else if (isJapanese) {
            projectContext = `\n## プロジェクト背景`;
            if (datasetName) {
              projectContext += `\nデータセット名：${datasetName}`;
            }
            if (datasetDescription) {
              projectContext += `\nプロジェクト説明：${datasetDescription}`;
            }
            projectContext += `\n生成されたデータがプロジェクトの目標と一致することを確認してください。`;
          } else {
            projectContext = `\n## 项目背景`;
            if (datasetName) {
              projectContext += `\n数据集名称：${datasetName}`;
            }
            if (datasetDescription) {
              projectContext += `\n项目描述：${datasetDescription}`;
            }
            projectContext += `\n请确保生成的数据与项目目标保持一致。`;
          }
        }

        // 基础提示词 - 支持多语言
        let basePrompt;
        
        if (isEnglish) {
          basePrompt = `You are a data annotation expert generating ${currentDatasetType.name} training data from documents.

## Task${projectContext}
- **Output Format**: ${formatDetails?.name || outputFormat} 
- **Data Type**: ${currentDatasetType.name}

${formatDetails ? `**Format Example**:
\`\`\`json
${formatDetails.example}
\`\`\`
` : 'Follow the specified format for data output.'}

Please generate accurate, relevant training data following the specified format.`;
        } else if (isJapanese) {
          basePrompt = `あなたは文書から${currentDatasetType.name}トレーニングデータを生成するデータアノテーションエキスパートです。

## タスク${projectContext}
- **出力形式**: ${formatDetails?.name || outputFormat} 
- **データタイプ**: ${currentDatasetType.name}

${formatDetails ? `**形式例**:
\`\`\`json
${formatDetails.example}
\`\`\`
` : '指定された形式でのデータ出力に従ってください。'}

指定された形式に従って正確で関連性のあるトレーニングデータを生成してください。`;
        } else {
          basePrompt = `您是一位从文档中生成${currentDatasetType.name}训练数据的数据标注专家。

## 任务${projectContext}
- **输出格式**：${formatDetails?.name || outputFormat} 
- **数据类型**：${currentDatasetType.name}

${formatDetails ? `**格式示例**：
\`\`\`json
${formatDetails.example}
\`\`\`
` : '请按照指定格式输出数据。'}

请按照指定格式生成准确、相关的训练数据。`;
        }

        // 根据数据集类型添加具体指导 - 支持多语言且提高质量要求
        switch (datasetType) {
          case 'qa-pairs':
            if (isEnglish) {
              basePrompt += `\n\nGenerate universal Q&A pairs that are meaningful even without the original document. Create general knowledge questions using document content as supporting evidence. AVOID context-dependent questions like "How many types are mentioned in the text?" or "What does the document say about..." Focus on standalone questions that test universal knowledge.`;
            } else if (isJapanese) {
              basePrompt += `\n\n元の文書がなくても意味のある汎用的な質問応答ペアを生成してください。文書内容を裏付け証拠として使用した一般知識の質問を作成します。「テキストに何種類記載されていますか？」や「文書では何について述べていますか？」などの文脈依存の質問は避けてください。汎用知識をテストする独立した質問に焦点を当てます。`;
            } else {
              basePrompt += `\n\n生成具有普适性的问答对，即使没有原始文档也有意义。创建以文档内容为支撑证据的通用知识问题。避免"文中提到了几种类型？"或"文档中说了什么？"等依赖上下文的问题。专注于测试通用知识的独立问题。`;
            }
            break;

          case 'instruction-tuning':
            if (isEnglish) {
              basePrompt += `\n\nGenerate instruction-tuning data with clear task descriptions and practical outputs. Focus on actionable instructions with relevant input-output pairs.`;
            } else if (isJapanese) {
              basePrompt += `\n\n明確なタスク記述と実用的な出力を含む指示チューニングデータを生成してください。関連する入力出力ペアを持つ実行可能な指示に焦点を当てます。`;
            } else {
              basePrompt += `\n\n生成具有明确任务描述和实用输出的指令微调数据。重点关注具有相关输入输出对的可操作指令。`;
            }
            break;

          case 'text-classification':
            if (isEnglish) {
              basePrompt += `\n\nGenerate text classification data with clear categories and representative text segments. Ensure accurate labeling and balanced distribution.`;
            } else if (isJapanese) {
              basePrompt += `\n\n明確なカテゴリと代表的なテキストセグメントを含むテキスト分類データを生成してください。正確なラベリングとバランスの取れた分布を確保します。`;
            } else {
              basePrompt += `\n\n生成具有明确分类和代表性文本片段的文本分类数据。确保准确标注和均衡分布。`;
            }
            break;

          case 'dialogue':
            if (isEnglish) {
              basePrompt += `\n\nGenerate natural multi-turn dialogues with logical coherence and informative content. Focus on practical conversation scenarios.`;
            } else if (isJapanese) {
              basePrompt += `\n\n論理的一貫性と情報豊富な内容を持つ自然な多ラウンド対話を生成してください。実践的な会話シナリオに焦点を当てます。`;
            } else {
              basePrompt += `\n\n生成具有逻辑连贯性和信息丰富内容的自然多轮对话。专注于实用的对话场景。`;
            }
            break;

          case 'domain-adaptation':
            if (isEnglish) {
              basePrompt += `\n\nGenerate domain-specific training data with professional terminology and practical applications. Focus on core domain knowledge and real-world scenarios.`;
            } else if (isJapanese) {
              basePrompt += `\n\n専門用語と実践的な応用を含むドメイン固有のトレーニングデータを生成してください。コアなドメイン知識と実世界のシナリオに焦点を当てます。`;
            } else {
              basePrompt += `\n\n生成包含专业术语和实践应用的领域特定训练数据。专注于核心领域知识和真实世界场景。`;
            }
            break;

          case 'reasoning':
            if (isEnglish) {
              basePrompt += `\n\nGenerate reasoning data with clear step-by-step logic and verifiable thinking processes. Show explicit reasoning chains from premise to conclusion.`;
            } else if (isJapanese) {
              basePrompt += `\n\n明確なステップバイステップの論理と検証可能な思考プロセスを持つ推論データを生成してください。前提から結論への明示的な推論チェーンを示します。`;
            } else {
              basePrompt += `\n\n生成具有清晰逐步逻辑和可验证思维过程的推理数据。展示从前提到结论的明确推理链。`;
            }
            break;

          case 'knowledge-distillation':
            if (isEnglish) {
              basePrompt += `\n\nGenerate knowledge distillation data by extracting core concepts and simplifying complex information while maintaining accuracy and comprehensibility.`;
            } else if (isJapanese) {
              basePrompt += `\n\nコア概念を抽出し、正確性と理解しやすさを維持しながら複雑な情報を簡略化して、知識蒸留データを生成してください。`;
            } else {
              basePrompt += `\n\n提取核心概念并简化复杂信息，同时保持准确性和可理解性，生成知识蒸馏数据。`;
            }
            break;

          case 'pretraining-data-cleaning':
            // 预训练数据清洗已在前面提前返回，不会执行到这里
            break;
        }

        return basePrompt;
      },

      // UI控制
      setIsLoading: (loading: boolean) => {
        set({ isLoading: loading });
      },

      setLoadingFiles: (loading: boolean) => {
        set({ loadingFiles: loading });
      },

      setLoadingCollections: (loading: boolean) => {
        set({ loadingCollections: loading });
      },

      setLoadingLLMConfigs: (loading: boolean) => {
        set({ loadingLLMConfigs: loading });
      },

      setProgress: (progress: number) => {
        set({ progress });
      },

      setError: (error: string | null) => {
        set({ error });
      },

      setShowFormatDetails: (show: boolean) => {
        set({ showFormatDetails: show });
      },

      setSelectedFormat: (format: string | null) => {
        set({ selectedFormat: format });
      },

      // 任务管理
      setTaskInfo: (taskInfo) => {
        set({ taskInfo });
      },

      // 业务逻辑
      // startGeneration功能已迁移到Step4PreviewConfirm组件内部处理

      resetState: () => {
        set(initialState);
      },
    }),
    {
      name: 'smart-dataset-creator-store', // devtools中显示的名称
    }
  )
); 